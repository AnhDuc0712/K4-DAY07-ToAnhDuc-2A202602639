from __future__ import annotations

import os
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
DEFAULT_CONFIG = {"strategy": "Heading/Section", "chunk_size": 500, "overlap": 50, "max_sentences": 3, "top_k": 3, "category": "all"}
STRATEGIES = ["Fixed-size", "Sentence", "Recursive", "Heading/Section"]
PLATFORMS = ["Tất cả", "Shopee", "TikTok Shop"]
AUDIENCES = ["Người bán", "Người mua", "Tất cả"]
CATEGORIES = ["all", "return_refund", "warranty", "seller_policy"]
SAMPLE_QUESTIONS = [
    "Người bán phải xử lý yêu cầu hoàn tiền trong bao lâu?",
    "Người bán có trách nhiệm gì về bảo hành?",
    "Hoàn tiền toàn bộ khác hoàn tiền một phần thế nào?",
    "Người mua có bao lâu để gửi lại hàng?",
]
PLATFORM_VALUES = {"Tất cả": "all", "Shopee": "shopee", "TikTok Shop": "tiktok_shop"}
AUDIENCE_VALUES = {"Tất cả": "all", "Người bán": "seller", "Người mua": "buyer"}
LABELS = {
    "shopee": "Shopee", "tiktok_shop": "TikTok Shop", "seller": "Người bán",
    "buyer": "Người mua", "both": "Người mua và người bán",
    "return_refund": "Trả hàng và hoàn tiền", "warranty": "Bảo hành", "seller_policy": "Quy định người bán",
}


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text:
        raise ValueError(f"Frontmatter không hợp lệ: {path.name}")
    raw, content = text[4:].split("\n---\n", 1)
    metadata: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, content.strip()


@st.cache_data(show_spinner=False)
def load_corpus() -> list[tuple[dict[str, str], str, str]]:
    return [(*parse_frontmatter(path), path.name) for path in sorted(DATA_DIR.glob("*.md"))]


def make_chunker(strategy: str, config: dict[str, Any]):
    if strategy == "Fixed-size":
        return FixedSizeChunker(config["chunk_size"], min(config["overlap"], config["chunk_size"] - 1))
    if strategy == "Sentence":
        return SentenceChunker(config["max_sentences"])
    if strategy == "Recursive":
        return RecursiveChunker(chunk_size=config["chunk_size"])
    return HeadingSectionChunker(chunk_size=config["chunk_size"])


def build_documents(records: list[tuple[dict[str, str], str, str]], config: dict[str, Any]) -> list[Document]:
    chunker = make_chunker(config["strategy"], config)
    documents: list[Document] = []
    for metadata, content, filename in records:
        doc_id = Path(filename).stem
        for index, chunk in enumerate(chunker.chunk(content)):
            documents.append(Document(
                id=f"{doc_id}#{index}",
                content=chunk,
                metadata={**metadata, "doc_id": doc_id, "chunk_id": index, "source": str(DATA_DIR / filename)},
            ))
    return documents


@st.cache_resource(show_spinner=False)
def get_local_embedder(model_name: str) -> LocalEmbedder:
    return LocalEmbedder(model_name=model_name)


@st.cache_resource(show_spinner=False)
def get_deepseek_client(api_key: str, base_url: str):
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=base_url, timeout=60.0, max_retries=2)


def build_index(records: list[tuple[dict[str, str], str, str]], config: dict[str, Any]):
    start = time.perf_counter()
    embedder = get_local_embedder(os.getenv("LOCAL_EMBEDDING_MODEL", DEFAULT_MODEL))
    documents = build_documents(records, config)
    store = EmbeddingStore(collection_name="streamlit_rag_v2", embedding_fn=embedder)
    store.add_documents(documents)
    return store, documents, embedder._backend_name, time.perf_counter() - start


def make_filter(platform: str, audience: str, category: str) -> dict[str, str]:
    values = {"platform": PLATFORM_VALUES[platform], "audience": AUDIENCE_VALUES[audience], "category": category}
    return {key: value for key, value in values.items() if value != "all"}


def call_deepseek(prompt: str) -> str:
    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Chưa cấu hình DeepSeek API key trong .env.")
    from openai import APIConnectionError, APITimeoutError, OpenAIError
    client = get_deepseek_client(api_key, (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip())
    try:
        response = client.chat.completions.create(
            model=(os.getenv("DEEPSEEK_MODEL") or "deepseek-flash").strip(),
            messages=[
                {"role": "system", "content": "Bạn là trợ lý chính sách dành cho người bán. Chỉ dùng context, không suy đoán. Trả lời tiếng Việt ngắn gọn, gắn citation [1], [2] hoặc [3]. Nếu thiếu thông tin, nói rõ không tìm thấy trong corpus."},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        return response.choices[0].message.content or ""
    except (APIConnectionError, APITimeoutError) as exc:
        raise RuntimeError("Không thể tạo câu trả lời tổng hợp lúc này.") from exc
    except OpenAIError as exc:
        raise RuntimeError(f"DeepSeek gặp lỗi {exc.__class__.__name__}.") from exc


def prompt_for(query: str, results: list[dict[str, Any]]) -> str:
    context = "\n\n".join(f"[{index}] {result['content']}" for index, result in enumerate(results, 1))
    return f"Trả lời câu hỏi chỉ dựa trên context sau. Citation phải dùng đúng số chunk.\n\nContext:\n{context}\n\nCâu hỏi: {query}\nTrả lời:"


def render_sources(sources: list[dict[str, Any]], developer_mode: bool) -> None:
    with st.expander(f"Xem nguồn tham khảo ({len(sources)})"):
        for index, result in enumerate(sources, 1):
            metadata = result["metadata"]
            title = metadata.get("title", "Chính sách thương mại điện tử")
            platform = LABELS.get(metadata.get("platform", ""), metadata.get("platform", ""))
            audience = LABELS.get(metadata.get("audience", ""), metadata.get("audience", ""))
            relevance = round(max(0.0, min(1.0, result["score"])) * 100)
            st.markdown(f"**[{index}] {title}**")
            st.caption(f"{platform} · {audience} · Độ liên quan {relevance}%")
            st.markdown(result["content"])
            if metadata.get("source_url"):
                st.link_button("Xem chính sách gốc", metadata["source_url"], width="content")
            if developer_mode:
                st.caption(f"doc_id={metadata.get('doc_id')} · chunk_id={metadata.get('chunk_id')} · raw_score={result['score']:.6f}")
            if index < len(sources):
                st.space("small")


def initialize_state() -> None:
    defaults = {
        "messages": [], "index_store": None, "index_documents": [], "index_signature": None,
        "index_stale": False, "index_error": None, "index_time": None, "embedding_backend": None,
        "dev_mode": False, "pending_question": None, "rebuild_requested": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def technical_config() -> dict[str, Any]:
    return {
        "strategy": st.session_state.get("dev_strategy", DEFAULT_CONFIG["strategy"]),
        "chunk_size": st.session_state.get("dev_chunk_size", DEFAULT_CONFIG["chunk_size"]),
        "overlap": st.session_state.get("dev_overlap", DEFAULT_CONFIG["overlap"]),
        "max_sentences": st.session_state.get("dev_max_sentences", DEFAULT_CONFIG["max_sentences"]),
        "top_k": st.session_state.get("dev_top_k", DEFAULT_CONFIG["top_k"]),
        "category": st.session_state.get("dev_category", DEFAULT_CONFIG["category"]),
    }


def render_sidebar(records: list[tuple[dict[str, str], str, str]]) -> None:
    st.sidebar.header("Bộ lọc")
    st.sidebar.caption("Nền tảng và đối tượng được chọn nhanh ở khu vực chính.")
    if st.sidebar.button("Xóa lịch sử trò chuyện", icon=":material/delete_sweep:"):
        st.session_state.messages = []
        st.rerun()
    st.sidebar.toggle("Chế độ dành cho nhà phát triển", key="dev_mode")
    if st.session_state.dev_mode:
        st.sidebar.subheader("Cấu hình kỹ thuật")
        st.sidebar.selectbox("Chunking strategy", STRATEGIES, key="dev_strategy", index=STRATEGIES.index(DEFAULT_CONFIG["strategy"]))
        st.sidebar.slider("chunk_size", 100, 1000, DEFAULT_CONFIG["chunk_size"], 50, key="dev_chunk_size")
        st.sidebar.slider("overlap", 0, 499, DEFAULT_CONFIG["overlap"], 10, key="dev_overlap")
        st.sidebar.slider("max_sentences_per_chunk", 1, 10, DEFAULT_CONFIG["max_sentences"], key="dev_max_sentences")
        st.sidebar.slider("top_k", 1, 10, DEFAULT_CONFIG["top_k"], key="dev_top_k")
        st.sidebar.selectbox("Category", CATEGORIES, key="dev_category")
        st.sidebar.caption(f"Embedding backend: {st.session_state.embedding_backend or 'chưa sẵn sàng'}")
        st.sidebar.caption(f"LLM backend: {os.getenv('DEEPSEEK_MODEL', 'deepseek-flash')}")
        st.sidebar.caption(f"Documents: {len(records)} · Chunks: {len(st.session_state.index_documents)}")
        if st.session_state.index_time is not None:
            st.sidebar.caption(f"Index time: {st.session_state.index_time:.2f}s")
        if st.session_state.index_stale and st.sidebar.button("Cập nhật chỉ mục", type="primary"):
            st.session_state.rebuild_requested = True


def ensure_default_index(records: list[tuple[dict[str, str], str, str]]) -> None:
    if st.session_state.index_store is not None or st.session_state.index_error:
        return
    with st.status("Đang chuẩn bị dữ liệu chính sách...", expanded=True) as status:
        try:
            st.write("Đang đọc tài liệu chính sách và xây dựng chỉ mục...")
            store, documents, backend, elapsed = build_index(records, DEFAULT_CONFIG)
            st.session_state.index_store, st.session_state.index_documents = store, documents
            st.session_state.embedding_backend, st.session_state.index_time = backend, elapsed
            st.session_state.index_signature = tuple(sorted(DEFAULT_CONFIG.items()))
            status.update(label="Hệ thống sẵn sàng", state="complete", expanded=False)
        except Exception as exc:
            st.session_state.index_error = str(exc)
            status.update(label="Không thể tạo chỉ mục", state="error", expanded=True)


def process_question(query: str, config: dict[str, Any], platform: str, audience: str) -> None:
    store: EmbeddingStore = st.session_state.index_store
    filters = make_filter(platform, audience, config["category"])
    retrieval_start = time.perf_counter()
    results = store.search_with_filter(query, top_k=config["top_k"], metadata_filter=filters)
    retrieval_time = time.perf_counter() - retrieval_start
    if not results:
        answer = "Không tìm thấy tài liệu phù hợp với bộ lọc hiện tại. Hãy thử chọn “Tất cả”."
        st.session_state.messages.append({"role": "assistant", "content": answer, "sources": [], "filter": filters})
        return
    agent = KnowledgeBaseAgent(store=store, llm_fn=call_deepseek)
    try:
        with st.spinner("Đang tổng hợp câu trả lời..."):
            llm_start = time.perf_counter()
            answer = agent.llm_fn(prompt_for(query, results))
            llm_time = time.perf_counter() - llm_start
    except RuntimeError:
        answer = "Không thể tạo câu trả lời tổng hợp lúc này. Kết quả tra cứu nguồn vẫn được hiển thị bên dưới."
        llm_time = None
    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": results, "filter": filters, "retrieval_time": retrieval_time, "llm_time": llm_time})


def main() -> None:
    load_dotenv(override=False)
    st.set_page_config(page_title="Trợ lý Chính sách Người bán", page_icon=":material/support_agent:", layout="centered")
    initialize_state()
    records = load_corpus()
    render_sidebar(records)
    ensure_default_index(records)
    st.title("Trợ lý Chính sách Người bán", anchor=False)
    st.caption("Tra cứu chính sách bảo hành, đổi trả và hoàn tiền trên Shopee và TikTok Shop.")
    if st.session_state.index_store is not None:
        st.markdown(":green-badge[● Hệ thống sẵn sàng]")
    elif st.session_state.index_error:
        st.markdown(":red-badge[● Không thể tải dữ liệu]")
        st.error("Không thể tải bộ tài liệu chính sách. Vui lòng kiểm tra thư mục data/ecommerce.")
        return
    else:
        st.markdown(":orange-badge[● Đang tải dữ liệu]")
        return

    config = technical_config()
    current_signature = tuple(sorted(config.items()))
    if st.session_state.index_signature and current_signature != st.session_state.index_signature:
        st.session_state.index_stale = True
    if st.session_state.index_stale:
        st.warning("Cấu hình kỹ thuật đã thay đổi. Hãy bật Developer Mode và bấm 'Cập nhật chỉ mục'.")
        if st.session_state.dev_mode and st.session_state.rebuild_requested:
            with st.spinner("Đang xây dựng lại chỉ mục..."):
                try:
                    store, documents, backend, elapsed = build_index(records, config)
                    st.session_state.index_store, st.session_state.index_documents = store, documents
                    st.session_state.embedding_backend, st.session_state.index_time = backend, elapsed
                    st.session_state.index_signature, st.session_state.index_stale = current_signature, False
                    st.session_state.rebuild_requested = False
                    st.rerun()
                except Exception as exc:
                    st.error(f"Không thể cập nhật chỉ mục: {exc}")

    st.subheader("Hỏi nhanh", anchor=False)
    platform = st.segmented_control("Nền tảng", PLATFORMS, default="Tất cả", key="platform_filter") or "Tất cả"
    audience = st.segmented_control("Đối tượng chính sách", AUDIENCES, default="Người bán", key="audience_filter") or "Người bán"
    if not st.session_state.messages:
        selected = st.pills("Câu hỏi mẫu", SAMPLE_QUESTIONS, key="sample_question")
        if selected:
            st.session_state.pending_question = selected
            st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("sources"):
                render_sources(message["sources"], st.session_state.dev_mode)
                if st.session_state.dev_mode:
                    with st.expander("Chi tiết Retrieval"):
                        st.json({"filter": message.get("filter", {}), "retrieval_seconds": message.get("retrieval_time"), "llm_seconds": message.get("llm_time"), "strategy": config["strategy"], "documents": len(records), "chunks": len(st.session_state.index_documents), "top_k": config["top_k"], "embedding_backend": st.session_state.embedding_backend, "llm_backend": "deepseek"})

    query = st.session_state.pop("pending_question", None)
    typed_query = st.chat_input(
        "Nhập câu hỏi về chính sách người bán...",
        key="chat_input",
        disabled=st.session_state.index_stale,
    )
    query = typed_query or query
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)
        with st.chat_message("assistant"):
            process_question(query, config, platform, audience)
            message = st.session_state.messages[-1]
            st.markdown(message["content"])
            if message.get("sources"):
                render_sources(message["sources"], st.session_state.dev_mode)
        st.rerun()


if __name__ == "__main__":
    main()
