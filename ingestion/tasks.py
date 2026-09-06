import logging

from celery import shared_task
from django.utils import timezone

from library.models import Book, Chapter, Chunk
from ingestion.parsers import parse_book
from ingestion.chunking import chunk_text, count_tokens
from ai.embeddings import embed_texts

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def process_book(self, book_id: int):
    """
    Full ingestion pipeline: parse file -> split into chapters -> chunk each
    chapter -> embed each chunk -> store everything. Runs on the Celery
    worker so a large upload never blocks a web request.
    """
    try:
        book = Book.objects.get(id=book_id)
    except Book.DoesNotExist:
        logger.error("process_book: book %s not found", book_id)
        return

    book.status = "processing"
    book.save(update_fields=["status"])

    try:
        with book.file.open("rb") as f:
            chapters_raw = parse_book(book.file_format, f)

        total_chunks = 0
        for chapter_index, (chapter_title, chapter_text) in enumerate(chapters_raw, start=1):
            chapter = Chapter.objects.create(
                book=book,
                order=chapter_index,
                title=chapter_title or f"Chapter {chapter_index}",
            )

            pieces = chunk_text(chapter_text)
            if not pieces:
                continue

            embeddings = embed_texts(pieces)

            chunk_objs = [
                Chunk(
                    book=book,
                    chapter=chapter,
                    order=total_chunks + i,
                    text=piece,
                    embedding=embedding,
                    token_count=count_tokens(piece),
                )
                for i, (piece, embedding) in enumerate(zip(pieces, embeddings))
            ]
            Chunk.objects.bulk_create(chunk_objs)
            total_chunks += len(chunk_objs)

        book.total_chunks = total_chunks
        book.status = "ready"
        book.updated_at = timezone.now()
        book.save(update_fields=["total_chunks", "status", "updated_at"])

    except Exception as exc:  # noqa: BLE001
        logger.exception("process_book failed for book %s", book_id)
        book.status = "failed"
        book.error_message = str(exc)[:2000]
        book.save(update_fields=["status", "error_message"])
        raise self.retry(exc=exc, countdown=30)


@shared_task
def reset_usage_counters():
    """
    Scheduled monthly (via Celery beat) to reset per-user usage counters that
    the billing tiers are enforced against. See accounts.models.Profile.
    """
    from accounts.models import Profile

    Profile.objects.update(
        books_processed_this_period=0,
        questions_asked_this_period=0,
        period_started_at=timezone.now(),
    )
