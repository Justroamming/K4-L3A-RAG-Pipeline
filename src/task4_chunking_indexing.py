"""
Task 4 — Chunking, embedding và indexing.

Hướng dẫn:
    1. Đọc toàn bộ Markdown trong data/standardized/.
    2. Chia văn bản bằng strategy đã chọn.
    3. Embed chunks bằng một provider duy nhất.
    4. Upsert vào ChromaDB với cosine distance.

Mỗi document/chunk phải theo docs/MODULE_CONTRACTS.md. ID cần ổn định để
chạy lại pipeline không tạo dữ liệu trùng. Task 5 phải dùng chung embed_texts().
"""

import os
import re
from pathlib import Path

import chromadb
from dotenv import load_dotenv


load_dotenv()

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(
    os.getenv("CHROMA_DIR", str(Path(__file__).parent.parent / "chroma_db"))
)

# Giải thích lựa chọn tham số trong báo cáo nhóm.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = 1024

COLLECTION_NAME = "rag_documents"
INDEX_BATCH_SIZE = 2
HNSW_BATCH_SIZE = 1000

_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed một list văn bản, dùng chung cho Task 4 và Task 5."""
    model = _get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return embeddings.tolist()


def get_collection():
    """Mở Chroma collection dùng cosine distance."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
            "hnsw:batch_size": HNSW_BATCH_SIZE,
            "hnsw:sync_threshold": HNSW_BATCH_SIZE,
        },
    )


def load_documents() -> list[dict]:
    """Đọc Markdown và trả về danh sách Document theo contract."""
    documents = []
    for path in STANDARDIZED_DIR.rglob("*.md"):
        if path.name == ".gitkeep":
            continue
        relative_path = path.relative_to(STANDARDIZED_DIR)
        doc_type = "legal" if "legal" in relative_path.parts else "news"
        content = path.read_text(encoding="utf-8")
        heading = re.search(r"^#\s+(.+?)\s*$", content, re.MULTILINE)
        source_match = re.search(r"^\*\*Source:\*\*\s*(\S+)", content, re.MULTILINE)
        source_url = source_match.group(1) if source_match else None
        documents.append({
            "id": relative_path.as_posix(),
            "content": content,
            "metadata": {
                "source": path.name,
                "title": heading.group(1).strip() if heading else path.stem,
                "doc_type": doc_type,
                "url": source_url if source_url and source_url.startswith(("http://", "https://")) else None,
            },
        })
    return documents


def _split_text(text: str) -> list[str]:
    """Split text on the largest available boundary, then add overlap."""
    separators = ["\n\n", "\n", ". ", " ", ""]
    pieces = [text]
    for separator in separators:
        if separator and any(len(piece) > CHUNK_SIZE for piece in pieces) and any(
            separator in piece for piece in pieces
        ):
            pieces = [part for piece in pieces for part in piece.split(separator) if part]
            break

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if len(piece) > CHUNK_SIZE:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(piece), CHUNK_SIZE - CHUNK_OVERLAP):
                chunks.append(piece[start : start + CHUNK_SIZE])
            continue

        candidate = piece if not current else f"{current} {piece}"
        if len(candidate) <= CHUNK_SIZE:
            current = candidate
            continue
        chunks.append(current)
        current = f"{current[-CHUNK_OVERLAP:]} {piece}".strip()

    if current:
        chunks.append(current)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chia Document thành chunks có id và chunk_index."""
    chunks = []
    for document in documents:
        texts = _split_text(document["content"])
        for index, text in enumerate(texts):
            if not text.strip():
                continue
            chunks.append({
                "id": f"{document['id']}::chunk-{index}",
                "content": text,
                "metadata": {**document["metadata"], "chunk_index": index},
            })
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Thêm embedding vào từng chunk."""
    texts = [chunk["content"] for chunk in chunks]
    vectors = embed_texts(texts)
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector
    return chunks


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert chunks vào ChromaDB."""
    collection = get_collection()
    for start in range(0, len(chunks), INDEX_BATCH_SIZE):
        batch = chunks[start : start + INDEX_BATCH_SIZE]
        collection.upsert(
            ids=[chunk["id"] for chunk in batch],
            documents=[chunk["content"] for chunk in batch],
            embeddings=[chunk["embedding"] for chunk in batch],
            metadatas=[chunk["metadata"] for chunk in batch],
        )


def run_pipeline() -> None:
    """Chạy load, chunk, embed và index."""
    documents = load_documents()
    print(f"Loaded {len(documents)} documents")
    chunks = chunk_documents(documents)
    print(f"Created {len(chunks)} chunks")
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks")


if __name__ == "__main__":
    run_pipeline()
