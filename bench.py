from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src import (
    Document,
    EmbeddingStore,
    FixedSizeChunker,
    HeadingSectionChunker,
    LocalEmbedder,
    OpenAIEmbedder,
    GeminiEmbedder,
    SentenceChunker,
)


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "ecommerce"

QUERIES: list[dict[str, Any]] = [
    {
        "id": 1,
        "query": "Người bán TikTok Shop phải xem xét yêu cầu trả hàng/hoàn tiền trong bao lâu? Nếu không xử lý đúng hạn thì điều gì xảy ra?",
        "metadata_filter": {"platform": "tiktok_shop", "audience": "seller", "category": "return_refund"},
        "gold": "1 ngày theo lịch; không hành động có thể dẫn tới phê duyệt tự động.",
    },
    {
        "id": 2,
        "query": "Sau khi yêu cầu trả hàng trên TikTok Shop được phê duyệt, người mua có bao nhiêu thời gian để gửi sản phẩm?",
        "metadata_filter": {"platform": "tiktok_shop", "audience": "seller", "category": "return_refund"},
        "gold": "10 ngày theo lịch; gửi trễ thì yêu cầu bị đóng và không hoàn tiền.",
    },
    {
        "id": 3,
        "query": "Trên TikTok Shop, hoàn tiền toàn bộ khác hoàn tiền một phần ở điểm nào đối với yêu cầu hậu mãi tiếp theo?",
        "metadata_filter": {"platform": "tiktok_shop", "audience": "seller", "category": "return_refund"},
        "gold": "Hoàn toàn bộ chặn yêu cầu tiếp theo; hoàn một phần vẫn cho phép yêu cầu và tổng hoàn không vượt giá trị đơn hàng.",
    },
    {
        "id": 4,
        "query": "Người bán trên Shopee có trách nhiệm gì về bảo hành và người mua cần đáp ứng điều kiện cơ bản nào?",
        "metadata_filter": {"platform": "shopee", "category": "warranty"},
        "gold": "Người bán tiếp nhận và công bố bảo hành; sản phẩm còn hạn, còn tem/phiếu và lỗi không do người mua.",
    },
    {
        "id": 5,
        "query": "Yêu cầu trả hàng/hoàn tiền trên Shopee thường được xử lý và hoàn tiền trong bao lâu?",
        "metadata_filter": {"platform": "shopee", "audience": "buyer", "category": "return_refund"},
        "gold": "Xử lý 3–5 ngày làm việc; hoàn tiền 1–14 ngày làm việc tùy phương thức thanh toán.",
    },
]


def parse_document(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text:
        raise ValueError(f"frontmatter không hợp lệ: {path.name}")
    raw_metadata, content = text[4:].split("\n---\n", 1)
    metadata: dict[str, str] = {}
    for line in raw_metadata.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, content.strip()


def load_documents() -> list[tuple[dict[str, str], str, Path]]:
    documents = []
    for path in sorted(DATA_DIR.glob("*.md")):
        metadata, content = parse_document(path)
        documents.append((metadata, content, path))
    return documents


def make_embedder(name: str):
    if name == "openai":
        return OpenAIEmbedder()
    if name == "local":
        return LocalEmbedder()
    if name == "gemini":
        return GeminiEmbedder()
    raise ValueError("backend phải là openai, local hoặc gemini; không dùng mock cho CP6")


def chunk_documents(
    documents: list[tuple[dict[str, str], str, Path]], strategy_name: str
) -> list[Document]:
    if strategy_name == "fixed_size":
        chunker = FixedSizeChunker(chunk_size=500, overlap=50)
    elif strategy_name == "sentence":
        chunker = SentenceChunker(max_sentences_per_chunk=3)
    elif strategy_name == "heading_section":
        chunker = HeadingSectionChunker(chunk_size=500)
    else:
        raise ValueError(f"strategy không hợp lệ: {strategy_name}")

    result: list[Document] = []
    for metadata, content, path in documents:
        chunks = chunker.chunk(content)
        source_doc_id = metadata.get("doc_id", path.stem)
        for index, chunk in enumerate(chunks):
            chunk_metadata = {**metadata, "doc_id": source_doc_id, "source_file": path.name}
            result.append(Document(f"{source_doc_id}#{index}", chunk, chunk_metadata))
    return result


def run_strategy(
    strategy_name: str,
    documents: list[tuple[dict[str, str], str, Path]],
    embedder: Any,
    include_unfiltered: bool,
) -> list[str]:
    lines = [f"===== STRATEGY: {strategy_name} ====="]
    chunks = chunk_documents(documents, strategy_name)
    store = EmbeddingStore(collection_name=f"benchmark_{strategy_name}", embedding_fn=embedder)
    store.add_documents(chunks)
    lines.append(f"chunks_loaded={store.get_collection_size()}")

    for item in QUERIES:
        lines.extend(_format_results(item, store, "WITH_FILTER", item["metadata_filter"]))
        if include_unfiltered and item["metadata_filter"]:
            lines.extend(_format_results(item, store, "WITHOUT_FILTER", None))
    return lines


def _format_results(
    item: dict[str, Any],
    store: EmbeddingStore,
    mode: str,
    metadata_filter: dict[str, str] | None,
) -> list[str]:
    if metadata_filter is None:
        results = store.search(item["query"], top_k=3)
    else:
        results = store.search_with_filter(item["query"], top_k=3, metadata_filter=metadata_filter)
    lines = [
        f"\nQuery {item['id']} [{mode}]: {item['query']}",
        f"Gold: {item['gold']}",
        f"Filter: {metadata_filter}",
    ]
    for rank, result in enumerate(results, start=1):
        lines.append(
            f"{rank}. score={result['score']:.6f} doc_id={result['metadata'].get('doc_id')} "
            f"chunk_id={result['id']}"
        )
        lines.append(f"   {result['content'].replace(chr(10), ' ')[:600]}")
    if not results:
        lines.append("NO RESULTS")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the five R2 queries across three chunking strategies.")
    parser.add_argument("--backend", required=True, choices=["openai", "local", "gemini"])
    parser.add_argument("--output", default="ket_qua_benchmark.txt")
    args = parser.parse_args()

    embedder = make_embedder(args.backend)
    print(f"Embedding backend: {getattr(embedder, '_backend_name', args.backend)}")
    documents = load_documents()
    lines = [f"Embedding backend: {getattr(embedder, '_backend_name', args.backend)}"]
    for strategy in ("fixed_size", "sentence", "heading_section"):
        lines.extend(run_strategy(strategy, documents, embedder, include_unfiltered=True))
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote benchmark output to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
