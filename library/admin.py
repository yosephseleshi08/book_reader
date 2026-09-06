from django.contrib import admin
from .models import Book, Chapter, Chunk, Progress, Question


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "file_format", "status", "total_chunks", "created_at")
    list_filter = ("status", "file_format")
    search_fields = ("title", "author", "owner__username")


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("book", "order", "title")


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "percent_complete", "last_read_at")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "kind", "created_at")
    list_filter = ("kind",)
