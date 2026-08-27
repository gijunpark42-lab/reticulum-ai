# chunker.py -- split a document into chunks and rank them by keyword relevance.
#
# WHY retrieval at all? The corpus is very uneven: the median document is ~7,000
# words but the long tail runs past 70,000 (Korean DART filings). Sending the whole
# document every time is simple but expensive, and on the long ones it buries the
# few sentences that actually answer the question. The agent instead SEARCHES.
#
# The ranking function is BM25 -- the standard keyword-ranking formula from
# information retrieval. It is written out here rather than imported so it can be
# read end to end. Two intuitions behind it:
#   * a word that appears in FEW chunks is more informative (that is the idf term)
#   * a word appearing 10x in a chunk is not 10x as relevant (that is the k1 term,
#     which saturates term frequency), and long chunks are penalised (the b term).

import math
import re
from typing import List

# Target chunk size in words. Small enough that a hit is precise, big enough to
# carry the surrounding sentence that gives a quote its meaning.
TARGET_WORDS = 220
MAX_WORDS = 400

_TOKEN = re.compile(r"[a-z0-9$%.]+")

# Very common English words carry no ranking information; dropping them keeps the
# idf term meaningful. Deliberately short -- domain words must NOT be dropped.
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "it", "that", "this", "as", "at",
    "by", "from", "we", "our", "you", "i", "so", "not", "have", "has", "had",
}


def tokenize(text: str) -> List[str]:
    """Lowercase words, keeping $ % and . so that '$207.4m' and '20%' survive."""
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


class Chunk:
    def __init__(self, chunk_id: int, text: str):
        self.id = chunk_id
        self.text = text
        self.tokens = tokenize(text)
        self.length = len(self.tokens)


def split_into_chunks(document: str) -> List[Chunk]:
    """Group paragraphs into ~TARGET_WORDS chunks without cutting a paragraph in half.

    Paragraph boundaries matter here: these files are speaker blocks and Q&A bullets,
    so a paragraph is usually one coherent thought. We only cut inside a paragraph
    when a single one is longer than MAX_WORDS.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", document) if p.strip()]

    # Any paragraph over MAX_WORDS gets broken on sentence boundaries first.
    pieces: List[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if len(words) <= MAX_WORDS:
            pieces.append(paragraph)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        buffer: List[str] = []
        count = 0
        for sentence in sentences:
            n = len(sentence.split())
            if count + n > TARGET_WORDS and buffer:
                pieces.append(" ".join(buffer))
                buffer, count = [], 0
            buffer.append(sentence)
            count += n
        if buffer:
            pieces.append(" ".join(buffer))

    # Now pack the pieces up to TARGET_WORDS each.
    chunks: List[Chunk] = []
    buffer: List[str] = []
    count = 0
    for piece in pieces:
        n = len(piece.split())
        if count + n > TARGET_WORDS and buffer:
            chunks.append(Chunk(len(chunks), "\n\n".join(buffer)))
            buffer, count = [], 0
        buffer.append(piece)
        count += n
    if buffer:
        chunks.append(Chunk(len(chunks), "\n\n".join(buffer)))
    return chunks


class BM25Index:
    """Keyword search over one document's chunks."""

    # Standard BM25 constants. k1 controls how fast term-frequency saturates,
    # b how strongly long chunks are penalised.
    K1 = 1.5
    B = 0.75

    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self.avg_length = (sum(c.length for c in chunks) / len(chunks)) if chunks else 0.0
        # document frequency: in how many chunks does each term appear at least once
        self.doc_freq = {}
        for chunk in chunks:
            for term in set(chunk.tokens):
                self.doc_freq[term] = self.doc_freq.get(term, 0) + 1
        self.n_chunks = len(chunks)

    def _idf(self, term: str) -> float:
        """Rare terms score higher. The +0.5 smoothing is the standard BM25 form."""
        df = self.doc_freq.get(term, 0)
        return math.log(1 + (self.n_chunks - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 4) -> List[Chunk]:
        query_terms = tokenize(query)
        if not query_terms or not self.chunks:
            return []
        scored = []
        for chunk in self.chunks:
            # term frequency inside this chunk
            freq = {}
            for token in chunk.tokens:
                freq[token] = freq.get(token, 0) + 1
            score = 0.0
            for term in query_terms:
                tf = freq.get(term, 0)
                if tf == 0:
                    continue
                norm = 1 - self.B + self.B * (chunk.length / self.avg_length or 1)
                score += self._idf(term) * (tf * (self.K1 + 1)) / (tf + self.K1 * norm)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]


def build_index(document: str) -> BM25Index:
    return BM25Index(split_into_chunks(document))
