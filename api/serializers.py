from rest_framework import serializers

from library.models import Book, Chapter, Progress, Question


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ["id", "title", "author", "file", "file_format", "status", "error_message", "total_chunks", "created_at"]
        read_only_fields = ["status", "error_message", "total_chunks", "created_at"]


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = ["id", "order", "title"]


class ProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Progress
        fields = ["id", "book", "last_chunk_order", "percent_complete", "last_read_at"]
        read_only_fields = ["last_read_at"]


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "book", "kind", "prompt", "answer", "source_chunk_ids", "created_at"]
        read_only_fields = ["answer", "source_chunk_ids", "created_at"]
