from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.db.models import Q
from .models import SubjectMaterial
from .serializers import (
    SubjectMaterialListSerializer,
    SubjectMaterialDetailSerializer,
)


class SubjectMaterialViewSet(viewsets.ModelViewSet):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['subject', 'teacher', 'class_group', 'center', 'is_published']
    search_fields = ['title', 'description']
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = SubjectMaterial.objects.select_related(
            'subject', 'teacher', 'class_group', 'center',
        )
        if hasattr(user, 'managed_center'):
            qs = qs.filter(center=user.managed_center)
        elif hasattr(user, 'teacher_profile'):
            qs = qs.filter(center=user.teacher_profile.center)
        elif hasattr(user, 'student_profile'):
            student = user.student_profile
            # Filter by center AND (student's class/subject materials OR global materials)
            visible = Q(class_group__isnull=True)
            if student.classe_id:
                visible |= Q(class_group__classe=student.classe)
            if student.class_group_id:
                visible |= Q(class_group=student.class_group)
            qs = qs.filter(
                center=student.center,
                is_published=True,
            ).filter(visible)
        elif user.is_staff:
            pass
        else:
            qs = qs.none()
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return SubjectMaterialListSerializer
        return SubjectMaterialDetailSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, 'teacher_profile'):
            teacher = user.teacher_profile
            serializer.save(
                teacher=teacher,
                center=teacher.center
            )
        else:
            serializer.save()
