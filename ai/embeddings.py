"""
Embedding generation for RAG. Uses OpenAI's embedding endpoint — swap this
module out if you'd rather run a local sentence-transformers model to cut
API costs at higher volume.
"""
from django.conf import settings
from openai import OpenAI

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = get_client()
    # Batch in groups of 100 to stay well under request size limits.
    all_embeddings: list[list[float]] = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=settings.EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([item.embedding for item in response.data])
    return all_embeddings


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
