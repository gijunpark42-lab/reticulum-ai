import os
import json
import requests
from dotenv import load_dotenv
from anthropic import Anthropic
from bs4 import BeautifulSoup


load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# strip markdown code fences and trailing prose, then parse JSON
def _parse_json_response(raw):
    raw = raw.strip()
    # remove markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    # extract just the outermost JSON object (first { to matching last })
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    return json.loads(raw)



# standard supply chain tiers (fixed order)
TIERS = [
    "equipment", "raw_material", "epiwafer", "component",
    "packaging", "switch_system", "oem", "hyperscaler", "ai_lab",
    "software"  # application/software layer — floats separately in graph
]


# use Opus to build a supply chain skeleton for one chain
def build_chain_skeleton(company, chain_focus):  # company + product/chain to map
    tiers_text = ", ".join(TIERS)  # tier list as a string for the prompt

    # streaming=True lets us use high max_tokens without hitting the SDK's 10-min timeout limit
    with client.messages.stream(
        model="claude-opus-4-8",  # smart model for accuracy
        max_tokens=16000,
        messages=[{
            "role": "user",
            "content": f"""You are a semiconductor supply chain analyst. Build the supply chain for {company}'s {chain_focus}.

Trace the chain from the earliest tier to final demand. Use ONLY these tier names, in this order: {tiers_text}

Rules for TIERS:
- SKIP tiers that don't apply. Some chains are short, some long.
- For EACH company, name the SPECIFIC product it makes in this chain (e.g. SK Hynix -> "HBM4 stacks", TSMC -> "CoWoS-L", Marvell -> "1.6T PAM4 DSP").
- The final tier must reach the end customer (hyperscaler and/or ai_lab).

Rules for EDGES (connects_to):
- This is a GRAPH, not a flat layer cake. Each player has specific outgoing edges to the companies it directly supplies or sells to.
- Edges usually go forward one tier (e.g. SK Hynix -> TSMC for packaging) but same-tier edges are allowed when real (e.g. a laser supplier -> transceiver assembler in the same component tier).
- Only create an edge where a REAL supply/customer relationship exists. Do NOT connect all companies in one tier to all companies in the next.
- A company with no real outgoing relationship in this chain gets "connects_to": [].
- "contracts" always starts empty [] — deal detail is added later from transcripts.

Each player must follow this exact shape:
{{
    "company": "company name",
    "product": "specific product in this chain",
    "connects_to": [
        {{"company": "target company name", "relationship": "one-line description of what flows", "contracts": []}}
    ],
    "quarterly_data": []
}}

Respond with ONLY a JSON object in this exact format, no other text:

{{
    "company": "{company}",
    "chain_focus": "{chain_focus}",
    "flow": [
        {{
            "tier": "tier_name",
            "players": [
                {{
                    "company": "company name",
                    "product": "specific product in this chain",
                    "connects_to": [
                        {{"company": "target company name", "relationship": "what flows on this edge", "contracts": []}}
                    ],
                    "quarterly_data": []
                }}
            ]
        }}
    ]
}}"""
        }]
    ) as stream:                    # "as stream" gives us a handle to read the response
        raw = stream.get_final_text()  # wait for the full response, return as one string

    return _parse_json_response(raw)



# save a chain to a JSON file inside the chains/ folder
def save_chain(chain_data, filename):  # the chain dictionary + filename (e.g. "nvidia_vera_rubin.json")
    os.makedirs("chains", exist_ok=True)  # create the folder if it doesn't exist
    path = "chains/" + filename  # put it inside the chains folder
    with open(path, "w", encoding="utf-8") as f:  # open in write mode
        json.dump(chain_data, f, indent=2)  # write the dictionary as nicely-formatted JSON
    print(f"Saved to {path}")  # confirm


# load a chain from a JSON file inside the chains/ folder
def load_chain(filename):  # filename to read
    path = "chains/" + filename  # look inside the chains folder
    with open(path, "r", encoding="utf-8") as f:  # open in read mode
        return json.load(f)  # read JSON and return as dictionary    

# use a transcript to add quarterly data and deal detail to a chain — ADD only, never remove
def analyze_with_transcript(chain, transcript, quarter_label):  # chain dict + transcript text + label like "NVDA Q1 2027"
    chain_json = json.dumps(chain)  # turn the chain into a string to send to Claude

    with client.messages.stream(
        model="claude-sonnet-4-6",  # cheaper model is fine for extraction
        max_tokens=32000,
        messages=[{
            "role": "user",
            "content": f"""You are a supply chain analyst. Here is a supply chain map (JSON) and a transcript (earnings call, news article, or event).

You have FOUR jobs. All are ADD-only — never remove or overwrite existing data.

JOB 1 — Add node-level figures to EXISTING companies:
If the transcript mentions a company already in the chain (revenue, growth %, capacity, demand, shortages), add a "quarterly_data" entry to that player.
Shape: {{"quarter": "{quarter_label}", "signal": "exact quote or paraphrase", "figure": "the number, or 'no specific figure'"}}

JOB 2 — Add deal detail to EXISTING edges:
Each player has a "connects_to" list of edges. If the transcript reveals a concrete deal, contract, or commitment on an existing edge (units shipped, $ value, delivery date, deal type), add a "contracts" entry to that edge.
Shape: {{"source": "{quarter_label}", "signal": "what was said", "units": "quantity or 'no specific figure'", "value": "$ amount or 'no specific figure'", "date_signed": "year/quarter or 'not stated'", "type": "supply agreement / deployment / partnership / etc."}}

JOB 3 — Add NEW companies revealed by the transcript:
If the transcript explicitly names a company that passes the litmus test (its stock directly benefits from this product being built and sold) and is NOT already in the chain, add it to the correct tier with empty connects_to and quarterly_data.
Shape: {{"company": "name", "product": "specific role in this chain", "connects_to": [], "quarterly_data": [{{...}}]}}
Tier names: equipment, raw_material, epiwafer, component, packaging, switch_system, oem, hyperscaler, ai_lab.
For cloud/neocloud use "hyperscaler". For AI model companies use "ai_lab".

JOB 4 — Add NEW edges revealed by the transcript:
If the transcript states a real supply or customer relationship between two companies already in the chain, and that edge does not yet exist in connects_to, add it.
Shape: {{"company": "target", "relationship": "what flows on this edge", "contracts": [{{...}}]}}

Global rules:
- DO NOT invent companies or deals. Only use what the transcript explicitly states.
- DO NOT add a company that is already in the chain — find it and update it instead. Check carefully for duplicates.
- Keep every existing node, edge, and data point intact. Only ADD.

Return ONLY the updated JSON, same format as input, no other text.

CHAIN:
{chain_json}

TRANSCRIPT:
{transcript}"""
        }]
    ) as stream:
        raw = stream.get_final_text()

    return _parse_json_response(raw)

def fetch_transcript(url, filename):  # the URL + filename (e.g. "nvda_q1_2027.txt")
    os.makedirs("transcripts", exist_ok=True)  # create the folder if it doesn't exist
    headers = {"User-Agent": "Mozilla/5.0"}  # pretend to be a browser
    response = requests.get(url, headers=headers)  # download the page
    soup = BeautifulSoup(response.content, "html.parser")  # parse the HTML
    paragraphs = soup.find_all("p")  # find all paragraph tags
    text = "\n\n".join(p.text for p in paragraphs)  # join into one string

    path = "transcripts/" + filename  # save inside the transcripts folder
    with open(path, "w", encoding="utf-8") as f:  # open in write mode
        f.write(text)  # save the transcript
    print(f"Saved transcript to {path}")  # confirm

    return text  # return it so we can use it right away

# read a saved transcript from the transcripts/ folder
def load_transcript(filename):  # filename to read
    path = "transcripts/" + filename  # look inside transcripts folder
    with open(path, "r", encoding="utf-8") as f:  # open in read mode
        return f.read()  # return the content as a string
    


# ── RUN TRANSCRIPT ENRICHMENT ────────────────────────────────────────────────
# This block only runs when you execute "python main.py" directly.
# It does NOT run when app.py imports from this file.
# Paste a URL, pick a filename/label, then run main.py.
# After it succeeds, comment the block out and add the next URL.

if __name__ == "__main__":
    chain = build_chain_skeleton(
        "TSMC / Samsung Foundry / Intel Foundry",
        "Advanced semiconductor foundry — contract wafer fabrication for AI chips at leading-edge "
        "nodes (TSMC N3/N2, Samsung SF3/SF2, Intel 18A). Trace from equipment suppliers "
        "(ASML EUV, Applied Materials, Lam Research, KLA, Tokyo Electron) and raw materials "
        "(silicon wafers from Shin-Etsu/SUMCO, photoresist from JSR/Shin-Etsu/TOK, "
        "process chemicals) through foundry fabs (TSMC, Samsung Foundry, Intel Foundry, "
        "GlobalFoundries, SMIC) to fabless chip designers — AI accelerators (NVIDIA, AMD, "
        "Broadcom, Marvell, Google TPU, AWS Trainium, Microsoft Maia) and logic chips — "
        "then on to packaging (CoWoS, SoIC) and final hyperscaler/OEM customers."
    )
    save_chain(chain, "foundry.json")
# ─────────────────────────────────────────────────────────────────────────────
