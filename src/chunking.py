from __future__ import annotations

import math
import re


class FixedSizeChunker:
    """
    Split text into fixed-size chunks with optional overlap.

    Rules:
        - Each chunk is at most chunk_size characters long.
        - Consecutive chunks share overlap characters.
        - The last chunk contains whatever remains.
        - If text is shorter than chunk_size, return [text].
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        step = self.chunk_size - self.overlap
        chunks: list[str] = []
        for start in range(0, len(text), step):
            chunk = text[start : start + self.chunk_size]
            chunks.append(chunk)
            if start + self.chunk_size >= len(text):
                break
        return chunks


class SentenceChunker:
    """
    Split text into chunks of at most max_sentences_per_chunk sentences.

    Sentence detection: split on ". ", "! ", "? " or ".\n".
    Strip extra whitespace from each chunk.
    """

    def __init__(self, max_sentences_per_chunk: int = 3) -> None:
        self.max_sentences_per_chunk = max(1, max_sentences_per_chunk)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip())]
        sentences = [sentence for sentence in sentences if sentence]
        return [
            " ".join(sentences[start : start + self.max_sentences_per_chunk])
            for start in range(0, len(sentences), self.max_sentences_per_chunk)
        ]


class RecursiveChunker:
    """
    Recursively split text using separators in priority order.

    Default separator priority:
        ["\n\n", "\n", ". ", " ", ""]
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(self, separators: list[str] | None = None, chunk_size: int = 500) -> None:
        self.separators = self.DEFAULT_SEPARATORS if separators is None else list(separators)
        self.chunk_size = chunk_size

    def chunk(self, text: str) -> list[str]:
        return self._split(text, self.separators)

    def _split(self, current_text: str, remaining_separators: list[str]) -> list[str]:
        text = current_text.strip()
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        separator = next(
            (item for item in remaining_separators if item and item in text),
            None,
        )
        if separator is None:
            return self._fixed_size_fallback(text)

        separator_index = remaining_separators.index(separator)
        lower_separators = remaining_separators[separator_index + 1 :]
        pieces = [piece.strip() for piece in text.split(separator)]
        pieces = [piece for piece in pieces if piece]

        chunks: list[str] = []
        pending: list[str] = []
        for piece in pieces:
            candidate = separator.join(pending + [piece]).strip()
            if pending and len(candidate) > self.chunk_size:
                chunks.append(separator.join(pending).strip())
                pending = []

            if len(piece) > self.chunk_size:
                if pending:
                    chunks.append(separator.join(pending).strip())
                    pending = []
                chunks.extend(self._split(piece, lower_separators))
            else:
                pending.append(piece)

        if pending:
            chunks.append(separator.join(pending).strip())
        return chunks

    def _fixed_size_fallback(self, text: str) -> list[str]:
        return [
            text[start : start + self.chunk_size]
            for start in range(0, len(text), self.chunk_size)
        ]


class HeadingSectionChunker:
    """Split Markdown by headings, recursively splitting long sections."""

    HEADING_PATTERN = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)

    def __init__(self, chunk_size: int = 500) -> None:
        self.chunk_size = chunk_size
        self._recursive = RecursiveChunker(chunk_size=chunk_size)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        headings = list(self.HEADING_PATTERN.finditer(text))
        if not headings:
            return self._recursive.chunk(text)

        sections: list[str] = []
        if headings[0].start() > 0 and text[: headings[0].start()].strip():
            sections.append(text[: headings[0].start()].strip())

        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            section = text[heading.start() : end].strip()
            sections.extend(self._split_section(section, heading.group().strip()))
        return sections

    def _split_section(self, section: str, heading: str) -> list[str]:
        if len(section) <= self.chunk_size:
            return [section]

        body = section[len(heading) :].strip()
        if not body:
            return self._recursive.chunk(section)
        body_chunk_size = max(1, self.chunk_size - len(heading) - 2)
        recursive = RecursiveChunker(chunk_size=body_chunk_size)
        return [f"{heading}\n\n{chunk}" for chunk in recursive.chunk(body)]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def compute_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    cosine_similarity = dot(a, b) / (||a|| * ||b||)

    Returns 0.0 if either vector has zero magnitude.
    """
    magnitude_a = math.sqrt(sum(value * value for value in vec_a))
    magnitude_b = math.sqrt(sum(value * value for value in vec_b))
    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0
    return _dot(vec_a, vec_b) / (magnitude_a * magnitude_b)


class ChunkingStrategyComparator:
    """Run all built-in chunking strategies and compare their results."""

    def compare(self, text: str, chunk_size: int = 200) -> dict:
        strategies = {
            "fixed_size": FixedSizeChunker(chunk_size=chunk_size, overlap=0),
            "by_sentences": SentenceChunker(max_sentences_per_chunk=3),
            "recursive": RecursiveChunker(chunk_size=chunk_size),
        }

        comparison: dict[str, dict] = {}
        for name, strategy in strategies.items():
            chunks = strategy.chunk(text)
            average_length = (
                sum(len(chunk) for chunk in chunks) / len(chunks) if chunks else 0.0
            )
            comparison[name] = {
                "count": len(chunks),
                "avg_length": average_length,
                "chunks": chunks,
            }
        return comparison
