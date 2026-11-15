from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from .models import Center, ClassRoom, Subject
from .serializers import (
    CenterListSerializer, CenterDetailSerializer,
    ClassRoomSerializer, SubjectSerializer,
)


class IsAdminOrManagerForCenter(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and request.user.is_staff

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            if hasattr(request.user, 'managed_center'):
                return request.user.managed_center == obj
            return request.user.is_staff
        return request.user.is_staff


class CenterViewSet(viewsets.ModelViewSet):
    def _get_action(self):
        action = getattr(self, 'action', None)
        if action is not None:
            return action

        request = getattr(self, 'request', None)
        if request is None:
            return None

        if request.method.lower() == 'get':
            kwargs = getattr(self, 'kwargs', {}) or {}
            if kwargs.get('pk') is not None:
                return 'retrieve'
            return 'list'

        return None

    def get_permissions(self):
        action = self._get_action()
        if action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [IsAdminOrManagerForCenter()]

    def get_authenticators(self):
        action = self._get_action()
        if action in ['list', 'retrieve']:
            return []
        return super().get_authenticators()

    def get_queryset(self):
        action = self._get_action()
        if action in ['list', 'retrieve']:
            return Center.objects.all()

        user = self.request.user
        if user.is_authenticated:
            if user.is_staff:
                return Center.objects.all()
            if hasattr(user, 'managed_center'):
                return Center.objects.filter(id=user.managed_center.id)
        return Center.objects.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return CenterListSerializer
        return CenterDetailSerializer

    def perform_create(self, serializer):
        serializer.save(manager=self.request.user)


class ClassRoomViewSet(viewsets.ModelViewSet):
    serializer_class = ClassRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return ClassRoom.objects.all()
        if hasattr(user, 'managed_center'):
            return ClassRoom.objects.filter(center=user.managed_center)
        if hasattr(user, 'teacher_profile'):
            return ClassRoom.objects.filter(center=user.teacher_profile.center)
        return ClassRoom.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, 'managed_center'):
            serializer.save(center=user.managed_center)
        else:
            serializer.save()


class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'managed_center'):
            return Subject.objects.filter(center=user.managed_center)
        if hasattr(user, 'teacher_profile'):
            return Subject.objects.filter(center=user.teacher_profile.center)
        if user.is_staff:
            return Subject.objects.all()
        return Subject.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, 'managed_center'):
            serializer.save(center=user.managed_center)
        else:
            serializer.save()
