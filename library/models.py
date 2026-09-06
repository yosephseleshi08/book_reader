from django.conf import settings
from django.db import models
from pgvector.django import VectorField


def book_upload_path(instance, filename):
    return f"books/{instance.owner_id}/{filename}"


class Book(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]
    FORMAT_CHOICES = [
        ("pdf", "PDF"),
        ("epub", "EPUB"),
        ("docx", "DOCX"),
        ("txt", "Plain text"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="books")
    title = models.CharField(max_length=500, blank=True, default="")
    author = models.CharField(max_length=500, blank=True, default="")
    file = models.FileField(upload_to=book_upload_path)
    file_format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, default="")
    total_chunks = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or self.file.name


class Chapter(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        ordering = ["order"]
        unique_together = ("book", "order")

    def __str__(self):
        return f"{self.book.title} — {self.title or f'Chapter {self.order}'}"


class Chunk(models.Model):
    """
    A chunk is a paragraph-sized slice of the book's text, embedded for
    retrieval-augmented generation. This is the unit RAG search operates on.
    """
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chunks")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="chunks", null=True, blank=True)
    order = models.PositiveIntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=1536, null=True, blank=True)
    token_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["book", "order"])]

    def __str__(self):
        return f"Chunk {self.order} of {self.book_id}"


class Progress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reading_progress")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="progress_entries")
    last_chunk_order = models.PositiveIntegerField(default=0)
    percent_complete = models.FloatField(default=0.0)
    last_read_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "book")

    def __str__(self):
        return f"{self.user} — {self.book} ({self.percent_complete:.0f}%)"


class Question(models.Model):
    """A logged Q&A or 'explain this' interaction, kept for history and usage metering."""
    KIND_CHOICES = [("explain", "Explain"), ("question", "Question"), ("quiz", "Quiz")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="questions")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="questions")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="question")
    prompt = models.TextField()
    answer = models.TextField(blank=True, default="")
    source_chunk_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind}: {self.prompt[:50]}"
