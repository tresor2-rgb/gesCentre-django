from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes as perm
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Teacher, Student, StudentRequest, Notification
from .serializers import (
    TeacherListSerializer, TeacherDetailSerializer,
    StudentListSerializer, StudentDetailSerializer,
    StudentRequestSerializer, StudentRequestProcessSerializer,
    StudentEnrollmentRequestSerializer, StudentResetPasswordSerializer,
    NotificationSerializer,
)
from .notifications import (
    generate_temp_password, generate_username,
    notify_student_credentials, send_email_credentials,
)

User = get_user_model()


class IsCenterManagerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff:
            return True
        if hasattr(user, 'managed_center'):
            center = user.managed_center
            if hasattr(obj, 'center'):
                return obj.center == center
            if hasattr(obj, 'student') and hasattr(obj.student, 'center'):
                return obj.student.center == center
        return False


class TeacherViewSet(viewsets.ModelViewSet):
    permission_classes = [IsCenterManagerOrAdmin]

    def get_serializer_class(self):
        if self.action == 'list':
            return TeacherListSerializer
        return TeacherDetailSerializer

    def get_queryset(self):
        user = self.request.user
        from django.db.models import Count
        qs = Teacher.objects.select_related('user', 'center').annotate(
            classes_count=Count('class_groups')
        )
        if user.is_staff:
            return qs
        if hasattr(user, 'managed_center'):
            return qs.filter(center=user.managed_center)
        return Teacher.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, 'managed_center'):
            serializer.save(center=user.managed_center)
        else:
            serializer.save()

    def create(self, request, *args, **kwargs):
        # Handle manual creation by manager
        user_data = request.data
        email = user_data.get('email', '').strip()
        first_name = user_data.get('first_name', '')
        last_name = user_data.get('last_name', '')
        speciality = user_data.get('speciality', user_data.get('specialization', ''))

        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({'detail': 'A user with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create Django User
        username = generate_username(first_name, last_name)
        temp_password = generate_temp_password()

        user = User.objects.create_user(
            username=email if email else username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='teacher',
            is_active=True # Active if created manually? Or maybe false?
                           # If manager creates them, they should be active.
        )
        user.set_password(temp_password)
        user.save()

        # Create Teacher Profile
        center = None
        if hasattr(request.user, 'managed_center'):
            center = request.user.managed_center

        teacher = Teacher.objects.create(
            user=user,
            center=center,
            speciality=speciality,
            is_active=True
        )

        # Send the generated credentials to the teacher's email
        center_name = center.name if center else ''
        email_sent = send_email_credentials(
            first_name, last_name, email, temp_password, center_name
        )

        # Return detail
        response_data = TeacherDetailSerializer(teacher).data
        response_data['account_created'] = True
        response_data['login_id'] = email
        response_data['temp_password'] = temp_password
        response_data['whatsapp_link'] = None
        response_data['email_sent'] = email_sent

        return Response(response_data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        teacher = self.get_object()
        user = teacher.user

        data = request.data
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
            user.username = data['email']
        user.save()

        if 'speciality' in data or 'specialization' in data:
            teacher.speciality = data.get('speciality', data.get('specialization', ''))
        teacher.save()

        return Response(TeacherDetailSerializer(teacher).data)

    @action(detail=True, methods=['post'])
    def assign_classrooms(self, request, pk=None):
        teacher = self.get_object()
        classroom_ids = request.data.get('classroom_ids', [])
        if not classroom_ids:
            return Response(
                {'detail': 'classroom_ids is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.is_staff:
            if hasattr(request.user, 'managed_center'):
                valid = teacher.center.classrooms.filter(id__in=classroom_ids).values_list('id', flat=True)
                classroom_ids = [cid for cid in classroom_ids if cid in valid]
        teacher.classrooms.add(*classroom_ids)
        return Response(TeacherDetailSerializer(teacher).data)

    @action(detail=True, methods=['post'])
    def remove_classrooms(self, request, pk=None):
        teacher = self.get_object()
        classroom_ids = request.data.get('classroom_ids', [])
        if not classroom_ids:
            return Response(
                {'detail': 'classroom_ids is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        teacher.classrooms.remove(*classroom_ids)
        return Response(TeacherDetailSerializer(teacher).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        teacher = self.get_object()
        teacher.is_active = True
        teacher.save()
        if teacher.user:
            teacher.user.is_active = True
            teacher.user.save()
        return Response(TeacherDetailSerializer(teacher).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        teacher = self.get_object()
        teacher.is_active = False
        teacher.save()
        if teacher.user:
            teacher.user.is_active = False
            teacher.user.save()
        return Response(TeacherDetailSerializer(teacher).data)


class StudentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsCenterManagerOrAdmin]

    def get_serializer_class(self):
        if self.action == 'list':
            return StudentListSerializer
        return StudentDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Student.objects.select_related('center', 'class_group').all()
        if user.is_staff:
            return queryset
        if hasattr(user, 'managed_center'):
            return queryset.filter(center=user.managed_center)
        return Student.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        center = None
        if hasattr(user, 'managed_center'):
            center = user.managed_center
        elif user.is_staff:
            center = serializer.validated_data.get('center')

        student = serializer.save(
            center=center,
            registration_type='manual',
            status='approved',
        )

        # Handle class group linking
        if 'class_group' in serializer.validated_data:
             student.class_group = serializer.validated_data['class_group']
             student.save()
        elif 'class_group_id' in self.request.data:
             student.class_group_id = self.request.data['class_group_id']
             student.save()

        temp_password = generate_temp_password()
        email = serializer.validated_data.get('email', '').strip()
        username = generate_username(student.first_name, student.last_name)

        student_user = User(
            username=username,
            email=email,
            first_name=student.first_name,
            last_name=student.last_name,
            phone=student.phone or '',
            role='student',
            is_active=True,
        )
        student_user.set_password(temp_password)
        student_user.save()

        student.user = student_user
        student.save()

        login_id = email if email else username
        center_name = center.name if center else ''
        notification_results = notify_student_credentials(
            student, login_id, temp_password, center_name
        )

        student._temp_login_id = login_id
        student._temp_password = temp_password
        student._whatsapp_link = notification_results.get('whatsapp_link')
        student._email_sent = notification_results.get('email_sent', False)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        student = serializer.instance

        response_data = StudentDetailSerializer(student).data
        response_data['account_created'] = True
        response_data['login_id'] = getattr(student, '_temp_login_id', '')
        response_data['temp_password'] = getattr(student, '_temp_password', '')
        response_data['whatsapp_link'] = getattr(student, '_whatsapp_link', None)
        response_data['email_sent'] = getattr(student, '_email_sent', False)

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        student = self.get_object()
        serializer = StudentResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not student.user:
            return Response(
                {'detail': 'Cet élève n\'a pas de compte utilisateur.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student.user.set_password(serializer.validated_data['new_password'])
        student.user.save()

        return Response({'detail': 'Mot de passe réinitialisé avec succès.'})

    @action(detail=False, methods=['post'])
    def register_manual(self, request):
        user = request.user
        if not hasattr(user, 'managed_center') and not user.is_staff:
            return Response(
                {'detail': 'Only center managers can register students.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = StudentDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        center = user.managed_center if hasattr(user, 'managed_center') else None
        student = serializer.save(
            center=center,
            registration_type='manual',
            status='approved',
        )

        # Handle class group linking
        if 'class_group' in serializer.validated_data:
             student.class_group = serializer.validated_data['class_group']
             student.save()
        elif 'class_group_id' in request.data:
             student.class_group_id = request.data['class_group_id']
             student.save()
        return Response(
            StudentDetailSerializer(student).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        student = self.get_object()
        if student.status == 'approved':
            return Response(StudentDetailSerializer(student).data)

        student.status = 'approved'
        student.save()

        # ACTIVATE DJANGO USER
        if student.user:
            student.user.is_active = True
            student.user.save()

        student.requests.filter(status='pending').update(status='approved', processed_at=timezone.now())

        return Response(StudentDetailSerializer(student).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        student = self.get_object()
        student.status = 'rejected'
        student.save()

        if student.user:
            student.user.is_active = False
            student.user.save()

        student.requests.filter(status='pending').update(status='rejected', processed_at=timezone.now())

        return Response(StudentDetailSerializer(student).data)


class StudentRequestViewSet(viewsets.ModelViewSet):
    serializer_class = StudentRequestSerializer
    permission_classes = [IsCenterManagerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        queryset = StudentRequest.objects.select_related('student', 'center').all()
        if user.is_staff:
            return queryset
        if hasattr(user, 'managed_center'):
            return queryset.filter(center=user.managed_center)
        return StudentRequest.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, 'managed_center'):
            serializer.save(center=user.managed_center)
        else:
            serializer.save()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        request_obj = self.get_object()
        process_serializer = StudentRequestProcessSerializer(data=request.data)
        process_serializer.is_valid(raise_exception=True)

        request_obj.status = 'approved'
        request_obj.processed_at = timezone.now()
        if process_serializer.validated_data.get('message'):
            request_obj.message = process_serializer.validated_data['message']
        request_obj.save()

        student = request_obj.student
        if student.status != 'approved':
            student.status = 'approved'
            if not student.center:
                student.center = request_obj.center
            student.save()

            # ACTIVATE DJANGO USER ON REQUEST APPROVAL
            if student.user:
                student.user.is_active = True
                student.user.save()

        return Response(StudentRequestSerializer(request_obj).data)

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        request_obj = self.get_object()
        process_serializer = StudentRequestProcessSerializer(data=request.data)
        process_serializer.is_valid(raise_exception=True)

        request_obj.status = 'suspended'
        request_obj.processed_at = timezone.now()
        if process_serializer.validated_data.get('message'):
            request_obj.message = process_serializer.validated_data['message']
        request_obj.save()

        student = request_obj.student
        if student.status != 'suspended':
            student.status = 'suspended'
            student.save()

        return Response(StudentRequestSerializer(request_obj).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        request_obj = self.get_object()
        process_serializer = StudentRequestProcessSerializer(data=request.data)
        process_serializer.is_valid(raise_exception=True)

        request_obj.status = 'rejected'
        request_obj.processed_at = timezone.now()
        if process_serializer.validated_data.get('message'):
            request_obj.message = process_serializer.validated_data['message']
        request_obj.save()

        student = request_obj.student
        if student.status != 'rejected':
            student.status = 'rejected'
            student.save()

        return Response(StudentRequestSerializer(request_obj).data)


@api_view(['POST'])
@perm([permissions.IsAuthenticated])
def student_enrollment_request(request):
    serializer = StudentEnrollmentRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user
    if not hasattr(user, 'student_profile'):
        return Response(
            {'detail': 'Profil élève non trouvé.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    student = user.student_profile
    center_id = serializer.validated_data['center_id']

    if StudentRequest.objects.filter(
        student=student, center_id=center_id, status='pending'
    ).exists():
        return Response(
            {'detail': 'Une demande est déjà en attente pour ce centre.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    request_obj = StudentRequest.objects.create(
        student=student,
        center_id=center_id,
        status='pending',
        message=serializer.validated_data.get('message', ''),
    )

    return Response(
        StudentRequestSerializer(request_obj).data,
        status=status.HTTP_201_CREATED,
    )


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'count': count})

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'updated': updated})
