import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Supply Chain",
  description:
    "The global AI & semiconductor web — every supplier, customer, and deal, connected.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
