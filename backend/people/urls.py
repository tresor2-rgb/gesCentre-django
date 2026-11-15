from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TeacherViewSet, StudentViewSet, StudentRequestViewSet,
    NotificationViewSet, student_enrollment_request,
)

router = DefaultRouter()
router.register(r'teachers', TeacherViewSet, basename='teacher')
router.register(r'students', StudentViewSet, basename='student')
router.register(r'student-requests', StudentRequestViewSet, basename='student-request')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('enrollment-request/', student_enrollment_request, name='enrollment-request'),
    path('', include(router.urls)),
]
