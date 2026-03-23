import os
import pickle

import faiss
import numpy as np
import pdfplumber
import requests
from docx import Document
from sentence_transformers import SentenceTransformer

# Config
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80
TOP_K = 4
INDEX_PATH = "faiss_index.bin"
CHUNKS_PATH = "chunks.pkl"
SUPPORTED_FILE_TYPES = (".pdf", ".md", ".doc", ".docx")

# Embedding model loaded once
_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def extract_text_from_pdf(file_path: str) -> str:
    """Extract all text from a PDF file."""
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_text_from_markdown(file_path: str) -> str:
    """Read Markdown or plain-text files."""
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unable to decode text file: {file_path}")


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a DOCX file."""
    document = Document(file_path)
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs)


def extract_text_from_doc(file_path: str) -> str:
    """
    Extract text from a legacy .doc file using Microsoft Word on Windows.
    """
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise ValueError(
            ".doc files require Microsoft Word on Windows. Install pywin32 or convert the file to .docx."
        ) from exc

    pythoncom.CoInitialize()
    word = None
    document = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        document = word.Documents.Open(os.path.abspath(file_path), ReadOnly=True)
        return document.Content.Text
    except Exception as exc:
        raise ValueError(
            f"Unable to read .doc file '{os.path.basename(file_path)}'. "
            "Make sure Microsoft Word is installed, or convert the file to .docx."
        ) from exc
    finally:
        if document is not None:
            document.Close(False)
        if word is not None:
            word.Quit()
        pythoncom.CoUninitialize()


def extract_text_from_file(file_path: str) -> str:
    """Extract text from a supported file type."""
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        return extract_text_from_pdf(file_path)
    if extension == ".md":
        return extract_text_from_markdown(file_path)
    if extension == ".docx":
        return extract_text_from_docx(file_path)
    if extension == ".doc":
        return extract_text_from_doc(file_path)

    raise ValueError(
        f"Unsupported file type '{extension}'. Supported types: {', '.join(SUPPORTED_FILE_TYPES)}"
    )


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def process_documents(file_paths: list[str]) -> list[dict]:
    """
    Process a list of document paths into chunk dicts with metadata.
    Each dict: { 'text': str, 'source': str, 'chunk_id': int }
    """
    all_chunks = []
    for file_path in file_paths:
        print(f"  Processing: {file_path}")
        text = extract_text_from_file(file_path)
        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append(
                {
                    "text": chunk,
                    "source": os.path.basename(file_path),
                    "chunk_id": i,
                }
            )
    print(f"  Total chunks created: {len(all_chunks)}")
    return all_chunks


def build_index(chunks: list[dict]) -> faiss.IndexFlatL2:
    """Embed all chunks and build a FAISS index."""
    embedder = get_embedder()
    texts = [c["text"] for c in chunks]
    print(f"  Embedding {len(texts)} chunks...")
    embeddings = embedder.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    print(f"  FAISS index built with {index.ntotal} vectors (dim={dim})")
    return index


def save_index(index: faiss.IndexFlatL2, chunks: list[dict]):
    faiss.write_index(index, INDEX_PATH)
    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(chunks, f)
    print(f"  Index saved to '{INDEX_PATH}' and chunks to '{CHUNKS_PATH}'")


def load_index():
    index = faiss.read_index(INDEX_PATH)
    with open(CHUNKS_PATH, "rb") as f:
        chunks = pickle.load(f)
    return index, chunks


def index_exists() -> bool:
    return os.path.exists(INDEX_PATH) and os.path.exists(CHUNKS_PATH)


def retrieve(query: str, index: faiss.IndexFlatL2, chunks: list[dict], top_k: int = TOP_K) -> list[dict]:
    """Embed the query and return top-k most relevant chunks."""
    embedder = get_embedder()
    query_vec = embedder.encode([query], convert_to_numpy=True).astype("float32")
    distances, indices = index.search(query_vec, top_k)

    results = []
    for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        chunk = chunks[idx].copy()
        chunk["rank"] = rank + 1
        chunk["score"] = float(dist)
        results.append(chunk)
    return results


def build_prompt(query: str, retrieved_chunks: list[dict]) -> str:
    context = "\n\n---\n\n".join(
        f"[Source: {c['source']} | Chunk {c['chunk_id']}]\n{c['text']}" for c in retrieved_chunks
    )
    return f"""You are a helpful assistant for a construction marketplace.
Answer the user's question using ONLY the information provided in the context below.
If the answer is not found in the context, say: "I couldn't find information about that in the provided documents."
Do NOT make up information or use outside knowledge.

=== CONTEXT ===
{context}

=== QUESTION ===
{query}

=== ANSWER ==="""


def generate_answer(query: str, retrieved_chunks: list[dict], api_key: str) -> str:
    """Call OpenRouter LLM to generate a grounded answer."""
    prompt = build_prompt(query, retrieved_chunks)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://mini-rag-app.streamlit.app",
        "X-Title": "Mini RAG Construction Assistant",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.2,
        "reasoning": {"exclude": True},
    }

    response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)

    if not response.ok:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = response.text
        raise ValueError(f"OpenRouter API error ({response.status_code}): {error_payload}")

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise ValueError(f"OpenRouter returned no choices: {data}")

    message = choices[0].get("message", {})
    content = message.get("content")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        joined_text = "".join(text_parts).strip()
        if joined_text:
            return joined_text

    raise ValueError(f"OpenRouter returned an unexpected response format: {data}")


def rag_query(query: str, index, chunks: list[dict], api_key: str) -> dict:
    """
    Run the full RAG pipeline for a query.
    Returns { 'query', 'retrieved_chunks', 'answer' }
    """
    retrieved = retrieve(query, index, chunks)
    answer = generate_answer(query, retrieved, api_key)
    return {"query": query, "retrieved_chunks": retrieved, "answer": answer}
