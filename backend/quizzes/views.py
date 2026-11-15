from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.utils import timezone
from .models import Quiz, QuizQuestion, QuizOption, QuizResult
from .serializers import (
    QuizListSerializer,
    QuizDetailSerializer,
    QuizQuestionListSerializer,
    QuizQuestionDetailSerializer,
    QuizQuestionPublicSerializer,
    QuizOptionSerializer,
    QuizResultSerializer,
    QuizSubmitSerializer,
)


class QuizViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['teacher', 'is_active']
    search_fields = ['title', 'description']
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Quiz.objects.select_related('teacher').prefetch_related('class_groups', 'questions', 'questions__options')
        if hasattr(user, 'managed_center'):
            qs = qs.filter(teacher__center=user.managed_center)
        elif hasattr(user, 'teacher_profile'):
            qs = qs.filter(teacher=user.teacher_profile)
        elif hasattr(user, 'student_profile'):
            student = user.student_profile
            if student.classe_id:
                qs = qs.filter(class_groups__classe=student.classe)
            elif student.class_group_id:
                qs = qs.filter(class_groups=student.class_group)
            else:
                qs = qs.filter(teacher__center=student.center)
        elif user.is_staff:
            pass
        else:
            qs = qs.none()
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return QuizListSerializer
        if self.action == 'submit_quiz':
            return QuizSubmitSerializer
        return QuizDetailSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, 'teacher_profile'):
            serializer.save(teacher=user.teacher_profile)
        else:
            serializer.save()

    @action(detail=True, methods=['post'], url_path='submit-quiz')
    def submit_quiz(self, request, pk=None):
        quiz = self.get_object()
        user = request.user

        if not hasattr(user, 'student_profile'):
            return Response(
                {'detail': 'Only students can submit quizzes.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        student = user.student_profile

        latest_result = QuizResult.objects.filter(student=student, quiz=quiz).first()
        if latest_result is not None and not latest_result.is_read_by_teacher:
            return Response(
                {'detail': 'Votre enseignant doit consulter votre résultat précédent avant que vous puissiez repasser ce quiz.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = QuizSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data['answers']

        score = 0
        for answer in answers:
            try:
                question = QuizQuestion.objects.get(id=answer['question_id'], quiz=quiz)
            except QuizQuestion.DoesNotExist:
                continue

            if question.question_type in ('qcm', 'true_false'):
                selected_id = answer.get('selected_option_id')
                if selected_id:
                    try:
                        option = QuizOption.objects.get(id=selected_id, question=question)
                        if option.is_correct:
                            score += question.points
                    except QuizOption.DoesNotExist:
                        pass
            elif question.question_type == 'short_answer':
                text_answer = answer.get('text_answer', '').strip().lower()
                # Find the correct option for short answer (usually just one with is_correct=True)
                correct_option = question.options.filter(is_correct=True).first()
                if correct_option and correct_option.option_text.strip().lower() == text_answer:
                    score += question.points

        result = QuizResult.objects.create(
            student=student,
            quiz=quiz,
            score=score,
            total_points=quiz.total_points,
        )

        if quiz.teacher and quiz.teacher.user:
            from people.models import Notification

            student_class = ''
            if student.classe_id:
                student_class = student.classe.name
            elif student.class_group_id:
                student_class = student.class_group.name
            elif student.class_name:
                student_class = student.class_name

            completed_local = timezone.localtime(result.completed_at)
            class_part = f' (Classe {student_class})' if student_class else ''
            Notification.objects.create(
                recipient=quiz.teacher.user,
                title='Nouvelle soumission de quiz',
                message=(
                    f"{student.first_name} {student.last_name}{class_part} a soumis "
                    f"« {quiz.title} » le {completed_local.strftime('%d/%m/%Y à %H:%M')}."
                ),
                notification_type='quiz_submission',
                link=f'/teacher/quizzes/{quiz.id}',
            )

        return Response(
            QuizResultSerializer(result).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='quiz-results')
    def quiz_results(self, request, pk=None):
        quiz = self.get_object()
        user = request.user

        if not hasattr(user, 'teacher_profile'):
            return Response(
                {'detail': 'Only teachers can view quiz results.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        results = list(QuizResult.objects.filter(quiz=quiz).select_related('student', 'student__user'))
        just_read = [r for r in results if not r.is_read_by_teacher]
        QuizResult.objects.filter(pk__in=[r.pk for r in results]).update(is_read_by_teacher=True)
        for r in results:
            r.is_read_by_teacher = True

        from people.models import Notification
        for r in just_read:
            if r.student.user:
                Notification.objects.create(
                    recipient=r.student.user,
                    title='Résultat de quiz consulté',
                    message=(
                        f"Votre enseignant a consulté votre résultat au quiz "
                        f"« {quiz.title} » : {r.score}/{r.total_points} points."
                    ),
                    notification_type='info',
                )
        serializer = QuizResultSerializer(results, many=True)
        return Response(serializer.data)


class QuizQuestionViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['quiz', 'question_type']
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        user = self.request.user

        if self.action == 'list':
            if hasattr(user, 'student_profile'):
                return QuizQuestionPublicSerializer
            return QuizQuestionListSerializer

        if hasattr(user, 'student_profile'):
            return QuizQuestionPublicSerializer
        return QuizQuestionDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = QuizQuestion.objects.select_related('quiz', 'quiz__teacher').prefetch_related('options')
        if hasattr(user, 'managed_center'):
            qs = qs.filter(quiz__teacher__center=user.managed_center)
        elif hasattr(user, 'teacher_profile'):
            qs = qs.filter(quiz__teacher=user.teacher_profile)
        elif hasattr(user, 'student_profile'):
            student = user.student_profile
            # Students can see questions if the quiz is active and assigned to their group (or any group in their center for now)
            # Actually, the QuizViewSet already filters by group, so we can follow similar logic here.
            if student.classe_id:
                qs = qs.filter(quiz__class_groups__classe=student.classe)
            elif student.class_group_id:
                qs = qs.filter(quiz__class_groups=student.class_group)
            else:
                qs = qs.filter(quiz__teacher__center=student.center)
            qs = qs.filter(quiz__is_active=True)
        elif user.is_staff:
            pass
        else:
            qs = qs.none()
        return qs


class QuizOptionViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['question', 'is_correct']
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        user = self.request.user
        if hasattr(user, 'student_profile'):
            return QuizOptionPublicSerializer
        return QuizOptionSerializer

    def get_queryset(self):
        user = self.request.user
        qs = QuizOption.objects.select_related('question', 'question__quiz', 'question__quiz__teacher')
        if hasattr(user, 'managed_center'):
            qs = qs.filter(question__quiz__teacher__center=user.managed_center)
        elif hasattr(user, 'teacher_profile'):
            qs = qs.filter(question__quiz__teacher=user.teacher_profile)
        elif hasattr(user, 'student_profile'):
            student = user.student_profile
            if student.classe_id:
                qs = qs.filter(question__quiz__class_groups__classe=student.classe)
            elif student.class_group_id:
                qs = qs.filter(question__quiz__class_groups=student.class_group)
            else:
                qs = qs.filter(question__quiz__teacher__center=student.center)
            qs = qs.filter(question__quiz__is_active=True)
        elif user.is_staff:
            pass
        else:
            qs = qs.none()
        return qs


class QuizResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuizResultSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['quiz', 'student']
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = QuizResult.objects.select_related('student', 'quiz', 'quiz__teacher')
        if hasattr(user, 'managed_center'):
            qs = qs.filter(quiz__teacher__center=user.managed_center)
        elif hasattr(user, 'teacher_profile'):
            qs = qs.filter(quiz__teacher=user.teacher_profile)
        elif hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile)
        elif user.is_staff:
            pass
        else:
            qs = qs.none()
        return qs
