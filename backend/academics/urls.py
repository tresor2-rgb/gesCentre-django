from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClasseViewSet, ClassGroupViewSet, ScheduleViewSet, AttendanceViewSet

router = DefaultRouter()
router.register(r'classes', ClasseViewSet, basename='classe')
router.register(r'class-groups', ClassGroupViewSet, basename='classgroup')
router.register(r'schedules', ScheduleViewSet, basename='schedule')
router.register(r'attendance', AttendanceViewSet, basename='attendance')

urlpatterns = [
    path('', include(router.urls)),
]
