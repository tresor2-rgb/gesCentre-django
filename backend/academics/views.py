from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.db.models import Q
from .models import ClassGroup, Schedule, Attendance, Classe
from .serializers import (
    ClassGroupListSerializer,
    ClassGroupDetailSerializer,
    ScheduleSerializer,
    AttendanceSerializer,
    AttendanceBulkSerializer,
    ClasseListSerializer,
    ClasseDetailSerializer,
)


class ClasseViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['center']
    search_fields = ['name']
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Classe.objects.prefetch_related('class_groups').distinct()
        if hasattr(user, 'managed_center'):
            qs = qs.filter(center=user.managed_center)
        elif hasattr(user, 'teacher_profile'):
            teacher = user.teacher_profile
            qs = qs.filter(class_groups__teacher=teacher).distinct()
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return ClasseListSerializer
        return ClasseDetailSerializer

    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        classe = self.get_object()
        from people.models import Student
        from people.serializers import StudentListSerializer
        students = Student.objects.filter(classe=classe, status='approved')
        serializer = StudentListSerializer(students, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, 'managed_center'):
            serializer.save(center=user.managed_center)
        else:
            serializer.save()


class ClassGroupViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['center', 'subject', 'teacher', 'classe']
    search_fields = ['name']
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = ClassGroup.objects.select_related('subject', 'teacher', 'classroom', 'center', 'classe')
        if hasattr(user, 'managed_center'):
            qs = qs.filter(center=user.managed_center)
        elif hasattr(user, 'teacher_profile'):
            teacher = user.teacher_profile
            qs = qs.filter(Q(teacher=teacher) | Q(classroom__in=teacher.classrooms.all())).distinct()
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return ClassGroupListSerializer
        return ClassGroupDetailSerializer

    @action(detail=True, methods=['get', 'post'], url_path='students')
    def students(self, request, pk=None):
        class_group = self.get_object()
        from people.models import Student
        from people.serializers import StudentListSerializer

        if request.method == 'POST':
            student_id = request.data.get('student_id')
            if not student_id:
                return Response(
                    {'detail': 'Le champ student_id est requis.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            student = Student.objects.filter(
                pk=student_id, center=class_group.center,
            ).first()
            if student is None:
                return Response(
                    {'detail': 'Élève introuvable dans ce centre.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            student.class_group = class_group
            if class_group.classe_id:
                student.classe = class_group.classe
            student.save()
            return Response(ClassGroupDetailSerializer(class_group).data)

        students = Student.objects.filter(status='approved')
        if class_group.classe_id:
            students = students.filter(classe=class_group.classe)
        else:
            students = students.filter(class_group=class_group)
        serializer = StudentListSerializer(students, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=['delete'],
        url_path=r'students/(?P<student_id>[^/.]+)',
    )
    def remove_student(self, request, pk=None, student_id=None):
        class_group = self.get_object()
        from people.models import Student

        student = Student.objects.filter(
            pk=student_id, center=class_group.center,
        ).first()
        if student is None:
            return Response(
                {'detail': 'Élève introuvable dans ce centre.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if class_group.classe_id and student.classe_id == class_group.classe_id:
            student.classe = None
        if student.class_group_id == class_group.id:
            student.class_group = None
        student.save()
        return Response(ClassGroupDetailSerializer(class_group).data)

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, 'managed_center'):
            serializer.save(center=user.managed_center)
        else:
            serializer.save()


class ScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = ScheduleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['class_group', 'day_of_week', 'classroom', 'teacher']
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Schedule.objects.select_related('class_group', 'classroom', 'teacher', 'class_group__subject').prefetch_related('class_group__students')
        if hasattr(user, 'managed_center'):
            qs = qs.filter(center=user.managed_center)
        elif hasattr(user, 'teacher_profile'):
            teacher = user.teacher_profile
            # Show schedules assigned to this teacher OR schedules for their classes
            qs = qs.filter(Q(teacher=teacher) | Q(class_group__teacher=teacher))
        elif hasattr(user, 'student_profile'):
            student = user.student_profile
            # Tous les cours (matières) de la classe de l'élève
            if student.classe_id:
                qs = qs.filter(class_group__classe=student.classe)
            elif student.class_group_id:
                qs = qs.filter(class_group=student.class_group)
            else:
                qs = qs.none()
        elif not user.is_staff:
            qs = qs.none()
        return qs


class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['class_group', 'student', 'date']
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Attendance.objects.select_related('class_group', 'student')
        if hasattr(user, 'managed_center'):
            qs = qs.filter(class_group__center=user.managed_center)
        elif hasattr(user, 'teacher_profile'):
            qs = qs.filter(class_group__center=user.teacher_profile.center)
        elif hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile)
        return qs

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        serializer = AttendanceBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        attendance_data = serializer.validated_data['attendance']
        created = []

        for item in attendance_data:
            obj, was_created = Attendance.objects.update_or_create(
                class_group_id=item['class_group'] if 'class_group' in item else request.data.get('class_group'),
                student_id=item['student'],
                date=item['date'],
                defaults={
                    'status': item['status'],
                    'remarks': item.get('remarks', ''),
                },
            )
            created.append(obj)

        return Response(
            AttendanceSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )
