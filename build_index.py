"""Builds index.json from the PDFs in the docs folder (same method as PoC 3).

Run this once whenever the policy PDFs change:   python build_index.py
It costs a fraction of a cent (about 15 small embedding requests).
"""
import os
import json
import glob
from pypdf import PdfReader
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768
CHUNK_WORDS = 120
OVERLAP = 25


def chunk_words(text, size=CHUNK_WORDS, overlap=OVERLAP):
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        chunks.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
        start += size - overlap
    return chunks


chunks = []
for path in sorted(glob.glob("docs/*.pdf")):
    for page_no, page in enumerate(PdfReader(path).pages, start=1):
        for piece in chunk_words(page.extract_text() or ""):
            chunks.append({"file": os.path.basename(path), "page": page_no, "text": piece})
print(f"Made {len(chunks)} chunks from the PDFs. Creating embeddings...")

for c in chunks:
    result = client.models.embed_content(
        model=EMBED_MODEL, contents=[c["text"]],
        config={"task_type": "RETRIEVAL_DOCUMENT", "output_dimensionality": EMBED_DIM},
    )
    c["vector"] = result.embeddings[0].values

with open("index.json", "w", encoding="utf-8") as f:
    json.dump({"embed_model": EMBED_MODEL, "embed_dim": EMBED_DIM, "chunks": chunks}, f)
print("Saved index.json with", len(chunks), "chunks.")
