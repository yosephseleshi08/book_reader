"""
Retrieval-augmented generation: pull the most relevant chunks for a book
(by vector similarity) and feed them to Claude to ground the response in
the actual text instead of letting the model hallucinate.
"""
from django.conf import settings
from anthropic import Anthropic
from pgvector.django import CosineDistance

from library.models import Chunk
from ai.embeddings import embed_query
from ai.prompts import EXPLAIN_SYSTEM_PROMPT, QA_SYSTEM_PROMPT, QUIZ_SYSTEM_PROMPT, build_context_block

_client = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def retrieve_chunks(book_id: int, query: str, top_k: int = 6) -> list[Chunk]:
    query_embedding = embed_query(query)
    return list(
        Chunk.objects.filter(book_id=book_id, embedding__isnull=False)
        .annotate(distance=CosineDistance("embedding", query_embedding))
        .order_by("distance")[:top_k]
    )


def _generate(system_prompt: str, user_prompt: str) -> str:
    client = get_client()
    response = client.messages.create(
        model=settings.GENERATION_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def explain_chunk(book_id: int, chunk_id: int) -> dict:
    chunk = Chunk.objects.get(id=chunk_id, book_id=book_id)
    # Pull a little surrounding context so the explanation isn't isolated.
    neighbors = Chunk.objects.filter(book_id=book_id, order__gte=chunk.order - 1, order__lte=chunk.order + 1)
    context = build_context_block([c.text for c in neighbors])
    answer = _generate(EXPLAIN_SYSTEM_PROMPT, f"Excerpt(s) to explain:\n\n{context}")
    return {"answer": answer, "source_chunk_ids": [c.id for c in neighbors]}


def answer_question(book_id: int, question: str, top_k: int = 6) -> dict:
    chunks = retrieve_chunks(book_id, question, top_k=top_k)
    if not chunks:
        return {"answer": "This book hasn't finished processing yet, so I don't have text to search.", "source_chunk_ids": []}
    context = build_context_block([c.text for c in chunks])
    prompt = f"Question: {question}\n\nRelevant excerpts:\n\n{context}"
    answer = _generate(QA_SYSTEM_PROMPT, prompt)
    return {"answer": answer, "source_chunk_ids": [c.id for c in chunks]}


def generate_quiz(book_id: int, topic: str = "", num_questions: int = 5, top_k: int = 8) -> dict:
    query = topic or "key ideas and events covered in this book"
    chunks = retrieve_chunks(book_id, query, top_k=top_k)
    context = build_context_block([c.text for c in chunks])
    prompt = (
        f"Generate {num_questions} multiple-choice comprehension questions "
        f"based on these excerpts:\n\n{context}\n\n"
        "Return the questions as a numbered list, each with 4 options "
        "labeled a-d, the correct option, and a one-sentence explanation."
    )
    answer = _generate(QUIZ_SYSTEM_PROMPT, prompt)
    return {"answer": answer, "source_chunk_ids": [c.id for c in chunks]}
