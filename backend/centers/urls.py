from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CenterViewSet, ClassRoomViewSet, SubjectViewSet

router = DefaultRouter()
router.register(r'centers', CenterViewSet, basename='center')
router.register(r'classrooms', ClassRoomViewSet, basename='classroom')
router.register(r'subjects', SubjectViewSet, basename='subject')

urlpatterns = [
    path('', include(router.urls)),
]
