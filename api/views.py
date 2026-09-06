from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from library.models import Book, Chapter, Progress, Question
from ingestion.tasks import process_book
from ai.rag import explain_chunk, answer_question, generate_quiz
from .serializers import BookSerializer, ChapterSerializer, ProgressSerializer, QuestionSerializer


FORMAT_BY_EXTENSION = {"pdf": "pdf", "epub": "epub", "docx": "docx", "txt": "txt"}


class BookViewSet(viewsets.ModelViewSet):
    serializer_class = BookSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users only ever see their own uploaded books — never another
        # user's copyrighted material, by design, not just by convention.
        return Book.objects.filter(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        profile = request.user.profile
        if not profile.can_process_book():
            return Response(
                {"detail": "You've hit your plan's book limit for this period. Upgrade to process more."},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = request.data.get("file")
        extension = uploaded_file.name.rsplit(".", 1)[-1].lower() if uploaded_file else ""
        file_format = FORMAT_BY_EXTENSION.get(extension)
        if not file_format:
            return Response({"detail": "Unsupported file type. Use PDF, EPUB, DOCX, or TXT."}, status=400)

        book = serializer.save(owner=request.user, file_format=file_format, status="pending")

        profile.books_processed_this_period += 1
        profile.save(update_fields=["books_processed_this_period"])

        process_book.delay(book.id)

        return Response(self.get_serializer(book).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def chapters(self, request, pk=None):
        book = self.get_object()
        chapters = book.chapters.all()
        return Response(ChapterSerializer(chapters, many=True).data)

    @action(detail=True, methods=["post"])
    def explain(self, request, pk=None):
        book = self.get_object()
        chunk_id = request.data.get("chunk_id")
        if not chunk_id:
            return Response({"detail": "chunk_id is required."}, status=400)
        if book.status != "ready":
            return Response({"detail": f"Book is still {book.status}."}, status=409)

        result = explain_chunk(book.id, chunk_id)
        question = Question.objects.create(
            user=request.user, book=book, kind="explain",
            prompt=f"Explain chunk {chunk_id}", answer=result["answer"],
            source_chunk_ids=result["source_chunk_ids"],
        )
        return Response(QuestionSerializer(question).data)

    @action(detail=True, methods=["post"])
    def ask(self, request, pk=None):
        book = self.get_object()
        profile = request.user.profile
        question_text = request.data.get("question", "").strip()

        if not question_text:
            return Response({"detail": "question is required."}, status=400)
        if not profile.can_ask_question():
            return Response(
                {"detail": "You've hit your plan's question limit for this period. Upgrade for more."},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        if book.status != "ready":
            return Response({"detail": f"Book is still {book.status}."}, status=409)

        result = answer_question(book.id, question_text)

        profile.questions_asked_this_period += 1
        profile.save(update_fields=["questions_asked_this_period"])

        question = Question.objects.create(
            user=request.user, book=book, kind="question",
            prompt=question_text, answer=result["answer"],
            source_chunk_ids=result["source_chunk_ids"],
        )
        return Response(QuestionSerializer(question).data)

    @action(detail=True, methods=["post"])
    def quiz(self, request, pk=None):
        book = self.get_object()
        if book.status != "ready":
            return Response({"detail": f"Book is still {book.status}."}, status=409)

        topic = request.data.get("topic", "")
        result = generate_quiz(book.id, topic=topic)
        question = Question.objects.create(
            user=request.user, book=book, kind="quiz",
            prompt=topic or "General quiz", answer=result["answer"],
            source_chunk_ids=result["source_chunk_ids"],
        )
        return Response(QuestionSerializer(question).data)


class ProgressViewSet(viewsets.ModelViewSet):
    serializer_class = ProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Progress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="update-for-book")
    def update_for_book(self, request):
        book_id = request.data.get("book")
        last_chunk_order = int(request.data.get("last_chunk_order", 0))

        book = Book.objects.get(id=book_id, owner=request.user)
        percent = 0.0
        if book.total_chunks:
            percent = min(100.0, (last_chunk_order / book.total_chunks) * 100)

        progress, _ = Progress.objects.update_or_create(
            user=request.user, book=book,
            defaults={"last_chunk_order": last_chunk_order, "percent_complete": percent},
        )
        return Response(ProgressSerializer(progress).data)


class QuestionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Question.objects.filter(user=self.request.user)
        book_id = self.request.query_params.get("book")
        if book_id:
            qs = qs.filter(book_id=book_id)
        return qs
