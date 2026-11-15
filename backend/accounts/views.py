from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Q
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

import secrets
import string

from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'user': UserSerializer(user).data,
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        login_id = serializer.validated_data['email']
        password = serializer.validated_data['password']

        user = User.objects.filter(
            Q(email__iexact=login_id) | Q(username__iexact=login_id)
        ).first()

        if user is not None:
            user = authenticate(request, username=user.username, password=password)
        else:
            user = None

        if user is None:
            return Response(
                {'error': 'Identifiant ou mot de passe incorrect.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'user': UserSerializer(user).data,
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'error': 'Le token refresh est requis.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {'detail': 'Déconnexion réussie.'},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {'error': 'Token invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({'detail': 'Mot de passe modifié avec succès.'})


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class CustomTokenRefreshView(BaseTokenRefreshView):
    """Custom token refresh that accepts 'refresh_token' or 'refresh'."""

    def post(self, request, *args, **kwargs):
        if 'refresh_token' in request.data and 'refresh' not in request.data:
            request.data['refresh'] = request.data['refresh_token']
        return super().post(request, *args, **kwargs)


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user = User.objects.get(username=email, is_active=True)

        alphabet = string.ascii_letters + string.digits + '!@#$%&*'
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        user.set_password(temp_password)
        user.save()

        return Response({
            'detail': 'Un nouveau mot de passe a été généré. '
                      'Vérifiez vos emails ou contactez votre centre.',
            'temp_password': temp_password,
        }, status=status.HTTP_200_OK)


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        from people.models import Teacher, Student, StudentRequest
        from centers.models import ClassRoom
        from academics.models import ClassGroup, Schedule, Attendance, Classe
        from quizzes.models import Quiz
        from django.utils import timezone
        from django.db.models import Count, Avg

        now = timezone.now()
        today_weekday = now.weekday()

        if hasattr(user, 'student_profile'):
            profile = user.student_profile
            center = profile.center

            if profile.classe:
                my_groups = ClassGroup.objects.filter(classe=profile.classe)
            else:
                my_groups = ClassGroup.objects.none()

            total_attendance = Attendance.objects.filter(
                student=profile
            ).count()
            if total_attendance > 0:
                present_count = Attendance.objects.filter(
                    student=profile, status='present'
                ).count()
                attendance_rate = round((present_count / total_attendance) * 100, 1)
            else:
                attendance_rate = 0.0

            quizzes_count = Quiz.objects.filter(
                class_groups__in=my_groups, is_active=True
            ).count()

            sessions_today = Schedule.objects.filter(
                class_group__in=my_groups, day_of_week=today_weekday, status='active'
            ).count()

            return Response({
                'total_groups': my_groups.count(),
                'quizzes_count': quizzes_count,
                'sessions_today': sessions_today,
                'attendance_rate': attendance_rate,
            })

        if hasattr(user, 'managed_center'):
            center = user.managed_center
        elif hasattr(user, 'teacher_profile'):
            center = user.teacher_profile.center
        else:
            return Response({'detail': 'Aucun centre associé.'}, status=400)

        teachers_count = Teacher.objects.filter(center=center, is_active=True).count()
        students_count = Student.objects.filter(center=center, status='approved').count()
        classrooms_count = ClassRoom.objects.filter(center=center, is_active=True).count()
        classes_count = Classe.objects.filter(center=center).count()
        subjects_assigned_count = ClassGroup.objects.filter(center=center).count()
        pending_requests = StudentRequest.objects.filter(center=center, status='pending').count()
        quizzes_count = Quiz.objects.filter(teacher__center=center).count()

        sessions_today = Schedule.objects.filter(
            center=center, day_of_week=today_weekday, status='active'
        ).count()

        # Calculate attendance rate for last 30 days
        last_month = now - timezone.timedelta(days=30)
        total_attendance = Attendance.objects.filter(
            class_group__center=center, date__gte=last_month
        ).count()
        if total_attendance > 0:
            present_count = Attendance.objects.filter(
                class_group__center=center, date__gte=last_month, status='present'
            ).count()
            attendance_rate = round((present_count / total_attendance) * 100, 1)
        else:
            attendance_rate = 0.0

        recent_students = list(
            Student.objects.filter(center=center)
            .order_by('-created_at')[:5]
            .values('id', 'first_name', 'last_name', 'status', 'created_at')
        )
        recent_requests = list(
            StudentRequest.objects.filter(center=center, status='pending')
            .order_by('-created_at')[:5]
            .values('id', 'student__first_name', 'student__last_name', 'status', 'created_at')
        )

        pending_teachers = Teacher.objects.filter(center=center, is_active=False).count()

        return Response({
            'total_students': students_count,
            'total_teachers': teachers_count,
            'total_classrooms': classrooms_count,
            'total_classes': classes_count,
            'total_subjects_assigned': subjects_assigned_count,
            'total_quizzes': quizzes_count,
            'pending_requests': pending_requests + pending_teachers,
            'sessions_today': sessions_today,
            'attendance_rate': attendance_rate,
            'recent_students': recent_students,
            'recent_requests': recent_requests,
        })
