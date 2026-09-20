from __future__ import annotations

import socket
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.agent import KnowledgeBaseAgent
from src.embeddings import (
    EMBEDDING_PROVIDER_ENV,
    GEMINI_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    GeminiEmbedder,
    LocalEmbedder,
    OpenAIEmbedder,
    _mock_embed,
)
from src.models import Document
from src.store import EmbeddingStore

_ORIGINAL_GETADDRINFO = socket.getaddrinfo


def _use_ipv4_for_deepseek(
    host: str,
    port: int,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
):
    """Force IPv4 for DeepSeek because IPv6 is reset on the current network."""
    if str(host).lower() == "api.deepseek.com":
        family = socket.AF_INET

    return _ORIGINAL_GETADDRINFO(
        host,
        port,
        family,
        type,
        proto,
        flags,
    )


socket.getaddrinfo = _use_ipv4_for_deepseek
def _configure_console_encoding() -> None:
    """Keep the Windows manual demo able to print Vietnamese text."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


SAMPLE_FILES = [
    "data/python_intro.txt",
    "data/vector_store_notes.md",
    "data/rag_system_design.md",
    "data/customer_support_playbook.txt",
    "data/chunking_experiment_report.md",
    "data/vi_retrieval_notes.md",
]


def load_documents_from_files(file_paths: list[str]) -> list[Document]:
    """Load documents from file paths for the manual demo."""
    allowed_extensions = {".md", ".txt"}
    documents: list[Document] = []

    for raw_path in file_paths:
        path = Path(raw_path)

        if path.suffix.lower() not in allowed_extensions:
            print(f"Skipping unsupported file type: {path} (allowed: .md, .txt)")
            continue

        if not path.exists() or not path.is_file():
            print(f"Skipping missing file: {path}")
            continue

        content = path.read_text(encoding="utf-8")
        documents.append(
            Document(
                id=path.stem,
                content=content,
                metadata={"source": str(path), "extension": path.suffix.lower()},
            )
        )

    return documents


def demo_llm(prompt: str) -> str:
    """A simple mock LLM for manual RAG testing."""
    preview = prompt[:400].replace("\n", " ")
    return f"[DEMO LLM] Generated answer from prompt preview: {preview}..."


def deepseek_llm(prompt: str) -> str:
    """Generate an answer using the DeepSeek Chat API."""
    from openai import OpenAI

    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
        timeout=60.0,
        max_retries=2,
    )

    response = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip(),
        messages=[
            {
                "role": "system",
                "content": (
                    "Chỉ trả lời dựa trên context được cung cấp. "
                    "Nếu context không đủ, hãy nói rõ không tìm thấy thông tin."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        stream=False,
    )
    return response.choices[0].message.content or ""


def run_manual_demo(question: str | None = None, sample_files: list[str] | None = None) -> int:
    files = sample_files or SAMPLE_FILES
    query = question or "Summarize the key information from the loaded files."

    print("=== Manual File Test ===")
    print("Accepted file types: .md, .txt")
    print("Input file list:")
    for file_path in files:
        print(f"  - {file_path}")

    docs = load_documents_from_files(files)
    if not docs:
        print("\nNo valid input files were loaded.")
        print("Create files matching the sample paths above, then rerun:")
        print("  python3 main.py")
        return 1

    print(f"\nLoaded {len(docs)} documents")
    for doc in docs:
        print(f"  - {doc.id}: {doc.metadata['source']}")

    load_dotenv(override=False)
    if os.getenv("DEEPSEEK_API_KEY"):
        default_provider = "local"
    elif os.getenv("OPENAI_API_KEY"):
        default_provider = "openai"
    else:
        default_provider = "mock"
    provider = os.getenv(EMBEDDING_PROVIDER_ENV, default_provider).strip().lower()
    if provider == "local":
        try:
            embedder = LocalEmbedder(model_name=os.getenv("LOCAL_EMBEDDING_MODEL", LOCAL_EMBEDDING_MODEL))
        except Exception:
            embedder = _mock_embed
    elif provider == "openai":
        try:
            embedder = OpenAIEmbedder(model_name=os.getenv("OPENAI_EMBEDDING_MODEL", OPENAI_EMBEDDING_MODEL))
        except Exception:
            embedder = _mock_embed
    elif provider == "gemini":
        try:
            embedder = GeminiEmbedder(model_name=os.getenv("GEMINI_EMBEDDING_MODEL", GEMINI_EMBEDDING_MODEL))
        except Exception:
            embedder = _mock_embed
    else:
        embedder = _mock_embed

    print(f"\nEmbedding backend: {getattr(embedder, '_backend_name', embedder.__class__.__name__)}")

    store = EmbeddingStore(collection_name="manual_test_store", embedding_fn=embedder)
    store.add_documents(docs)

    print(f"\nStored {store.get_collection_size()} documents in EmbeddingStore")
    print("\n=== EmbeddingStore Search Test ===")
    print(f"Query: {query}")
    search_results = store.search(query, top_k=3)
    for index, result in enumerate(search_results, start=1):
        print(f"{index}. score={result['score']:.3f} source={result['metadata'].get('source')}")
        print(f"   content preview: {result['content'][:120].replace(chr(10), ' ')}...")

    print("\n=== KnowledgeBaseAgent Test ===")
    llm_provider = os.getenv(
        "LLM_PROVIDER",
        "deepseek" if os.getenv("DEEPSEEK_API_KEY") else "openai",
    ).strip().lower()
    use_real_llm = (
        (llm_provider == "deepseek" and bool(os.getenv("DEEPSEEK_API_KEY")))
        or (llm_provider == "openai" and bool(os.getenv("OPENAI_API_KEY")))
    )
    llm_fn = deepseek_llm if use_real_llm else demo_llm
    print(f"LLM backend: {llm_provider if use_real_llm else 'demo'}")
    agent = KnowledgeBaseAgent(store=store, llm_fn=llm_fn)
    print(f"Question: {query}")
    print("Agent answer:")
    print(agent.answer(query, top_k=3))
    return 0


def main() -> int:
    _configure_console_encoding()
    question = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else None
    return run_manual_demo(question=question)


if __name__ == "__main__":
    raise SystemExit(main())
