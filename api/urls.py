from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .views import BookViewSet, ProgressViewSet, QuestionViewSet

router = DefaultRouter()
router.register("books", BookViewSet, basename="book")
router.register("progress", ProgressViewSet, basename="progress")
router.register("questions", QuestionViewSet, basename="question")

urlpatterns = [
    path("auth/token/", obtain_auth_token, name="api-token-auth"),
    path("", include(router.urls)),
]
