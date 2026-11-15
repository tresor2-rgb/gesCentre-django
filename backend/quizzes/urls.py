from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    QuizViewSet,
    QuizQuestionViewSet,
    QuizOptionViewSet,
    QuizResultViewSet,
)

router = DefaultRouter()
router.register(r'quizzes', QuizViewSet, basename='quiz')
router.register(r'questions', QuizQuestionViewSet, basename='quizquestion')
router.register(r'options', QuizOptionViewSet, basename='quizoption')
router.register(r'results', QuizResultViewSet, basename='quizresult')

urlpatterns = [
    path('', include(router.urls)),
]
