"""
Splits chapter text into overlapping chunks sized for embedding + retrieval.
Overlap keeps context from being severed mid-idea at chunk boundaries.
"""
import re

TARGET_TOKENS = 600
OVERLAP_TOKENS = 80

_encoding = None
_encoding_unavailable = False


def _get_encoding():
    """
    Lazily loads the tiktoken encoding on first use, and caches it. tiktoken
    downloads its vocab file on first call in some environments — if that
    fails (offline build step, blocked egress, etc.) fall back to a rough
    chars/4 estimate rather than crashing the whole ingestion pipeline.
    """
    global _encoding, _encoding_unavailable
    if _encoding_unavailable:
        return None
    if _encoding is None:
        try:
            import tiktoken

            _encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:  # noqa: BLE001
            _encoding_unavailable = True
            return None
    return _encoding


def _token_len(text: str) -> int:
    encoding = _get_encoding()
    if encoding is not None:
        return len(encoding.encode(text))
    return max(1, len(text) // 4)  # rough fallback estimate


def split_into_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def chunk_text(text: str, target_tokens: int = TARGET_TOKENS, overlap_tokens: int = OVERLAP_TOKENS) -> list[str]:
    paragraphs = split_into_paragraphs(text)
    if not paragraphs:
        return []

    chunks = []
    current_paragraphs: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _token_len(para)

        if current_tokens + para_tokens > target_tokens and current_paragraphs:
            chunks.append("\n\n".join(current_paragraphs))
            # Carry the tail of the previous chunk forward for overlap.
            overlap_text = current_paragraphs[-1]
            overlap_len = _token_len(overlap_text)
            if overlap_len <= overlap_tokens:
                current_paragraphs = [overlap_text]
                current_tokens = overlap_len
            else:
                current_paragraphs = []
                current_tokens = 0

        current_paragraphs.append(para)
        current_tokens += para_tokens

    if current_paragraphs:
        chunks.append("\n\n".join(current_paragraphs))

    return chunks


def count_tokens(text: str) -> int:
    return _token_len(text)
