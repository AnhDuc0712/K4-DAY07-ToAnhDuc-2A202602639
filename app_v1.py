from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from src import (
    Document,
    EmbeddingStore,
    FixedSizeChunker,
    HeadingSectionChunker,
    KnowledgeBaseAgent,
    LocalEmbedder,
    RecursiveChunker,
    SentenceChunker,
)


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "ecommerce"
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
STRATEGIES = ["Fixed-size", "Sentence", "Recursive", "Heading/Section"]
PLATFORMS = ["all", "shopee", "tiktok_shop"]
AUDIENCES = ["all", "buyer", "seller", "both"]
CATEGORIES = ["all", "return_refund", "warranty", "seller_policy"]
SAMPLE_QUESTIONS = [
    "Người bán TikTok Shop phải xử lý yêu cầu trả hàng trong bao lâu?",
    "Hoàn tiền toàn bộ khác hoàn tiền một phần như thế nào?",
    "Người bán Shopee có trách nhiệm gì về bảo hành?",
    "Người mua cần đáp ứng điều kiện nào để được bảo hành?",
    "Sau khi yêu cầu trả hàng được chấp nhận, người mua có bao lâu để gửi hàng?",
]


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text:
        raise ValueError(f"Frontmatter không hợp lệ: {path.name}")
    raw, content = text[4:].split("\n---\n", 1)
    metadata: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, content.strip()


@st.cache_data(show_spinner=False)
def load_corpus() -> list[tuple[dict[str, str], str, str]]:
    records = []
    for path in sorted(DATA_DIR.glob("*.md")):
        metadata, content = parse_frontmatter(path)
        records.append((metadata, content, path.name))
    return records


def make_chunker(strategy: str, chunk_size: int, overlap: int, max_sentences: int):
    if strategy == "Fixed-size":
        return FixedSizeChunker(chunk_size=chunk_size, overlap=min(overlap, chunk_size - 1))
    if strategy == "Sentence":
        return SentenceChunker(max_sentences_per_chunk=max_sentences)
    if strategy == "Recursive":
        return RecursiveChunker(chunk_size=chunk_size)
    return HeadingSectionChunker(chunk_size=chunk_size)


def build_documents(
    records: list[tuple[dict[str, str], str, str]],
    strategy: str,
    chunk_size: int,
    overlap: int,
    max_sentences: int,
) -> list[Document]:
    chunker = make_chunker(strategy, chunk_size, overlap, max_sentences)
    documents: list[Document] = []
    for metadata, content, filename in records:
        doc_id = Path(filename).stem
        chunks = chunker.chunk(content)
        for index, chunk in enumerate(chunks):
            documents.append(
                Document(
                    id=f"{doc_id}#{index}",
                    content=chunk,
                    metadata={
                        **metadata,
                        "doc_id": doc_id,
                        "chunk_id": index,
                        "source": str(DATA_DIR / filename),
                    },
                )
            )
    return documents


@st.cache_resource(show_spinner=False)
def get_local_embedder(model_name: str) -> LocalEmbedder:
    return LocalEmbedder(model_name=model_name)


@st.cache_resource(show_spinner=False)
def get_deepseek_client(api_key: str, base_url: str):
    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url, timeout=60.0, max_retries=2)


def active_filter(platform: str, audience: str, category: str) -> dict[str, str]:
    values = {"platform": platform, "audience": audience, "category": category}
    return {key: value for key, value in values.items() if value != "all"}


def call_deepseek(prompt: str) -> str:
    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Thiếu DEEPSEEK_API_KEY trong .env")
    from openai import APIConnectionError, APITimeoutError, OpenAIError

    client = get_deepseek_client(
        api_key,
        (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip(),
    )
    try:
        response = client.chat.completions.create(
            model=(os.getenv("DEEPSEEK_MODEL") or "deepseek-flash").strip(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý chính sách thương mại điện tử. "
                        "Chỉ dùng context được cung cấp, không suy đoán. "
                        "Trả lời tiếng Việt, ngắn gọn, và trích dẫn chunk bằng [1], [2], [3]. "
                        "Nếu context không đủ, nói rõ không tìm thấy trong corpus."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        return response.choices[0].message.content or ""
    except (APIConnectionError, APITimeoutError) as exc:
        raise RuntimeError("Không kết nối được DeepSeek. Retrieval evidence vẫn được giữ lại.") from exc
    except OpenAIError as exc:
        raise RuntimeError(f"DeepSeek trả về lỗi API: {exc.__class__.__name__}") from exc


def build_prompt(query: str, results: list[dict[str, Any]]) -> str:
    context = "\n\n".join(f"[{index}] {item['content']}" for index, item in enumerate(results, 1))
    return (
        "Trả lời câu hỏi chỉ dựa trên context sau. Mỗi nhận định cần gắn citation [1], [2] hoặc [3].\n\n"
        f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
    )


def render_evidence(results: list[dict[str, Any]]) -> None:
    st.subheader("Nguồn bằng chứng")
    for index, result in enumerate(results, 1):
        metadata = result["metadata"]
        title = metadata.get("title", metadata.get("doc_id", "Không rõ tài liệu"))
        with st.expander(f"[{index}] {title} — score {result['score']:.4f}"):
            st.write(f"**doc_id:** `{metadata.get('doc_id', '')}`")
            st.write(f"**chunk_id:** `{metadata.get('chunk_id', '')}`")
            st.write(f"**platform:** `{metadata.get('platform', '')}`")
            st.write(f"**audience:** `{metadata.get('audience', '')}`")
            st.write(f"**category:** `{metadata.get('category', '')}`")
            st.markdown(result["content"])
            source_url = metadata.get("source_url")
            if source_url:
                st.markdown(f"[Mở nguồn chính thức]({source_url})")


def sidebar_config(records: list[tuple[dict[str, str], str, str]]) -> dict[str, Any]:
    st.sidebar.header("Cấu hình retrieval")
    strategy = st.sidebar.selectbox("Chunking strategy", STRATEGIES)
    chunk_size = st.sidebar.slider("chunk_size", 100, 1000, 500, 50)
    overlap = st.sidebar.slider("overlap", 0, max(0, chunk_size - 1), min(50, chunk_size - 1), 10)
    max_sentences = st.sidebar.slider("max_sentences_per_chunk", 1, 10, 3)
    top_k = st.sidebar.slider("top_k", 1, 10, 3)
    platform = st.sidebar.selectbox("Platform", PLATFORMS)
    audience = st.sidebar.selectbox("Audience", AUDIENCES)
    category = st.sidebar.selectbox("Category", CATEGORIES)
    config = {
        "strategy": strategy,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "max_sentences": max_sentences,
        "top_k": top_k,
        "filter": active_filter(platform, audience, category),
    }
    signature = tuple(config.items())
    if st.session_state.get("config_signature") != signature:
        st.session_state["config_signature"] = signature
        st.session_state["store"] = None
        st.session_state["documents"] = []
    st.sidebar.caption(f"Corpus: {len(records)} tài liệu")
    st.sidebar.caption(f"Embedding: {os.getenv('LOCAL_EMBEDDING_MODEL', DEFAULT_MODEL)}")
    st.sidebar.caption(f"LLM: {os.getenv('DEEPSEEK_MODEL', 'deepseek-flash')}")
    if st.sidebar.button("Tạo lại Vector Store", type="primary"):
        start = time.perf_counter()
        try:
            model_name = os.getenv("LOCAL_EMBEDDING_MODEL", DEFAULT_MODEL)
            embedder = get_local_embedder(model_name)
            documents = build_documents(records, strategy, chunk_size, overlap, max_sentences)
            store = EmbeddingStore(collection_name="streamlit_rag", embedding_fn=embedder)
            store.add_documents(documents)
            st.session_state["store"] = store
            st.session_state["documents"] = documents
            st.session_state["index_time"] = time.perf_counter() - start
            st.session_state["embedding_backend"] = embedder._backend_name
            st.rerun()
        except Exception as exc:
            st.session_state["store"] = None
            st.sidebar.error(f"Không tạo được local embedding/vector store: {exc}")
    return config


def main() -> None:
    load_dotenv(override=False)
    st.set_page_config(page_title="RAG Policy Assistant", page_icon="📚", layout="wide")
    records = load_corpus()
    config = sidebar_config(records)
    store: EmbeddingStore | None = st.session_state.get("store")
    documents: list[Document] = st.session_state.get("documents", [])

    st.title("Trợ lý Chính sách Bảo hành & Hậu mãi")
    st.caption("Hỏi đáp dựa trên tài liệu chính sách Shopee và TikTok Shop.")
    st.caption("Mọi câu trả lời phải được truy vết về tài liệu nguồn.")

    col1, col2, col3, col4 = st.sidebar.columns(4)
    col1.metric("Tài liệu", len(records))
    col2.metric("Chunks", len(documents))
    col3.metric("Embedding", "Local")
    col4.metric("LLM", "DeepSeek")

    sample = st.selectbox("Câu hỏi mẫu", ["— Tự nhập câu hỏi —", *SAMPLE_QUESTIONS])
    query = st.chat_input("Nhập câu hỏi về chính sách...") or (sample if sample != "— Tự nhập câu hỏi —" else "")
    if not query:
        st.info("Hãy tạo Vector Store ở sidebar, sau đó nhập câu hỏi.")
        return
    if store is None:
        st.warning("Vector Store chưa được tạo hoặc cấu hình đã thay đổi. Hãy bấm 'Tạo lại Vector Store'.")
        return

    applied_filter = config["filter"]
    retrieval_start = time.perf_counter()
    results = store.search_with_filter(query, top_k=config["top_k"], metadata_filter=applied_filter)
    retrieval_time = time.perf_counter() - retrieval_start
    st.subheader("Câu trả lời")
    agent = KnowledgeBaseAgent(store=store, llm_fn=call_deepseek)
    answer = None
    llm_time = None
    try:
        llm_start = time.perf_counter()
        answer = agent.llm_fn(build_prompt(query, results))
        llm_time = time.perf_counter() - llm_start
        st.markdown(answer)
    except RuntimeError as exc:
        st.warning(str(exc))
        st.info("Bạn vẫn có thể kiểm tra các chunk evidence bên dưới.")

    render_evidence(results)
    st.subheader("Metadata filter đang áp dụng")
    st.code(applied_filter or "{}", language="python")
    with st.expander("Chi tiết Retrieval"):
        st.json(
            {
                "query": query,
                "strategy": config["strategy"],
                "chunk_parameters": {
                    "chunk_size": config["chunk_size"],
                    "overlap": config["overlap"],
                    "max_sentences_per_chunk": config["max_sentences"],
                },
                "total_documents": len(records),
                "total_chunks": len(documents),
                "top_k": config["top_k"],
                "metadata_filter": applied_filter,
                "embedding_index_seconds": st.session_state.get("index_time"),
                "retrieval_seconds": retrieval_time,
                "llm_seconds": llm_time,
                "embedding_backend": st.session_state.get("embedding_backend", "local"),
                "llm_backend": "deepseek",
            }
        )


if __name__ == "__main__":
    main()
