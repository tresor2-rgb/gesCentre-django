from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from academics.models import Attendance, Schedule
from centers.models import Center
from materials.models import SubjectMaterial
from people.models import Notification, StudentRequest
from quizzes.models import Quiz, QuizResult

from ..decorators import student_required
from ..services import notify_quiz_submission
from ..utils import get_student, student_groups


def _student(request):
    return get_student(request.user)


def _available_quizzes(student):
    groups = student_groups(student)
    if not groups.exists():
        return Quiz.objects.none()
    return Quiz.objects.filter(
        class_groups__in=groups, is_active=True,
    ).distinct().select_related('teacher__user')


@student_required
def dashboard(request):
    student = _student(request)
    if student is None:
        messages.error(request, "Profil élève introuvable.")
        return redirect('web:home')

    if student.status != 'approved':
        return render(request, 'web/student/pending.html', {
            'student': student,
            'center': student.center,
            'requests': student.requests.select_related('center').order_by('-created_at'),
        })

    today = timezone.localdate()
    groups = student_groups(student)
    total_attendance = Attendance.objects.filter(student=student).count()
    present_count = Attendance.objects.filter(student=student, status='present').count()
    attendance_rate = round(present_count / total_attendance * 100, 1) if total_attendance else 0

    quizzes = list(_available_quizzes(student))
    for quiz in quizzes:
        quiz.latest_result = QuizResult.objects.filter(student=student, quiz=quiz).first()
        quiz.can_take = quiz.latest_result is None or quiz.latest_result.is_read_by_teacher
    available = [quiz for quiz in quizzes if quiz.can_take]

    materials = SubjectMaterial.objects.filter(
        center=student.center, is_published=True,
    ).filter(
        Q(class_group__isnull=True)
        | Q(class_group__classe=student.classe)
        | Q(class_group=student.class_group)
    ).select_related('subject', 'teacher__user').distinct()

    return render(request, 'web/student/dashboard.html', {
        'student': student,
        'center': student.center,
        'today': today,
        'groups': groups,
        'attendance_rate': attendance_rate,
        'quizzes_count': len(available),
        'materials_count': materials.count(),
        'sessions_today': Schedule.objects.filter(
            class_group__in=groups, day_of_week=today.weekday(), status='active',
        ).select_related('class_group', 'classroom', 'class_group__subject').order_by('start_time'),
        'quizzes': available[:5],
        'materials': materials[:5],
        'recent_results': QuizResult.objects.filter(
            student=student,
        ).select_related('quiz').order_by('-completed_at')[:5],
    })


@student_required
def centers(request):
    student = _student(request)
    if student is None:
        return redirect('web:home')

    search = request.GET.get('q', '').strip()
    centers_qs = Center.objects.filter(is_active=True).select_related('manager')
    if search:
        centers_qs = centers_qs.filter(
            Q(name__icontains=search) | Q(address__icontains=search),
        )

    pending_center_ids = set(
        StudentRequest.objects.filter(
            student=student, status='pending',
        ).values_list('center_id', flat=True)
    )
    approved_center_ids = set(
        StudentRequest.objects.filter(
            student=student, status='approved',
        ).values_list('center_id', flat=True)
    )

    return render(request, 'web/student/centers.html', {
        'student': student,
        'centers': centers_qs,
        'search': search,
        'pending_center_ids': pending_center_ids,
        'approved_center_ids': approved_center_ids,
    })


@student_required
def center_request(request, pk):
    student = _student(request)
    if student is None:
        return redirect('web:home')
    center = get_object_or_404(Center, pk=pk, is_active=True)

    if request.method != 'POST':
        return redirect('web:student_centers')

    if StudentRequest.objects.filter(
        student=student, center=center, status='pending',
    ).exists():
        messages.warning(request, "Une demande est déjà en attente pour ce centre.")
        return redirect('web:student_centers')

    message = request.POST.get('message', '').strip()
    student_request = StudentRequest.objects.create(
        student=student,
        center=center,
        status='pending',
        message=message or "Demande d'inscription.",
    )
    if center.manager_id:
        Notification.objects.create(
            recipient=center.manager,
            title="Nouvelle demande d'inscription",
            message=(
                f"{student.first_name} {student.last_name} souhaite rejoindre "
                f"« {center.name} »."
            ),
            notification_type='info',
            link='/manager/requests/?status=pending',
        )
    messages.success(
        request,
        f"Votre demande d'inscription à « {center.name} » a été envoyée.",
    )
    return redirect('web:student_centers')


@student_required
def classes(request):
    student = _student(request)
    if student is None:
        return redirect('web:home')
    if student.status != 'approved':
        return redirect('web:student_dashboard')

    groups = student_groups(student)
    return render(request, 'web/student/classes.html', {
        'student': student,
        'groups': groups,
        'classe': student.classe,
    })


@student_required
def schedule(request):
    student = _student(request)
    if student is None:
        return redirect('web:home')
    if student.status != 'approved':
        return redirect('web:student_dashboard')

    groups = student_groups(student)
    items = Schedule.objects.filter(
        class_group__in=groups, status='active',
    ).select_related('class_group', 'classroom', 'class_group__subject', 'teacher__user').order_by(
        'day_of_week', 'start_time',
    )
    grouped = {day: [] for day, _ in Schedule.DAY_CHOICES}
    for item in items:
        grouped[item.day_of_week].append(item)

    return render(request, 'web/student/schedule.html', {
        'student': student,
        'week': [(label, grouped[value]) for value, label in Schedule.DAY_CHOICES],
        'total': items.count(),
        'today_weekday': timezone.localdate().weekday(),
    })


@student_required
def quizzes(request):
    student = _student(request)
    if student is None:
        return redirect('web:home')
    if student.status != 'approved':
        return redirect('web:student_dashboard')

    quizzes_qs = list(_available_quizzes(student))
    for quiz in quizzes_qs:
        quiz.latest_result = QuizResult.objects.filter(student=student, quiz=quiz).first()
        quiz.can_take = quiz.latest_result is None or quiz.latest_result.is_read_by_teacher

    return render(request, 'web/student/quizzes.html', {
        'student': student,
        'quizzes': quizzes_qs,
        'results': QuizResult.objects.filter(student=student).select_related(
            'quiz', 'quiz__teacher__user',
        ).order_by('-completed_at'),
    })


@student_required
def quiz_take(request, pk):
    student = _student(request)
    if student is None:
        return redirect('web:home')
    if student.status != 'approved':
        return redirect('web:student_dashboard')

    quiz = get_object_or_404(
        Quiz, pk=pk, is_active=True,
    )
    groups = student_groups(student)
    if not quiz.class_groups.filter(pk__in=groups.values('pk')).exists():
        messages.error(request, "Ce quiz n'est pas destiné à votre classe.")
        return redirect('web:student_quizzes')

    latest_result = QuizResult.objects.filter(student=student, quiz=quiz).first()
    if latest_result is not None and not latest_result.is_read_by_teacher:
        messages.warning(
            request,
            "Votre enseignant doit consulter votre résultat précédent avant que "
            "vous puissiez repasser ce quiz.",
        )
        return redirect('web:student_quizzes')

    questions = list(quiz.questions.prefetch_related('options'))
    if not questions:
        messages.warning(request, "Ce quiz ne contient encore aucune question.")
        return redirect('web:student_quizzes')

    if request.method == 'POST':
        score = 0
        for question in questions:
            if question.question_type in ('qcm', 'true_false'):
                selected = request.POST.get(f'q_{question.pk}_option')
                if selected:
                    option = question.options.filter(pk=selected).first()
                    if option is not None and option.is_correct:
                        score += question.points
            else:
                text_answer = request.POST.get(f'q_{question.pk}_text', '').strip().lower()
                correct = question.options.filter(is_correct=True).first()
                if correct is not None and correct.option_text.strip().lower() == text_answer:
                    score += question.points

        result = QuizResult.objects.create(
            student=student,
            quiz=quiz,
            score=score,
            total_points=quiz.total_points,
        )
        notify_quiz_submission(result)
        messages.success(
            request,
            f"Quiz soumis. Votre score : {result.score}/{result.total_points}.",
        )
        return redirect('web:student_quiz_result', pk=result.pk)

    return render(request, 'web/student/quiz_take.html', {
        'student': student,
        'quiz': quiz,
        'questions': questions,
    })


@student_required
def quiz_result(request, pk):
    student = _student(request)
    if student is None:
        return redirect('web:home')
    result = get_object_or_404(QuizResult, pk=pk, student=student)
    return render(request, 'web/student/quiz_result.html', {
        'student': student,
        'result': result,
        'quiz': result.quiz,
    })


@student_required
def materials(request):
    student = _student(request)
    if student is None:
        return redirect('web:home')
    if student.status != 'approved':
        return redirect('web:student_dashboard')

    materials_qs = SubjectMaterial.objects.filter(
        center=student.center, is_published=True,
    ).filter(
        Q(class_group__isnull=True)
        | Q(class_group__classe=student.classe)
        | Q(class_group=student.class_group)
    ).select_related('subject', 'teacher__user', 'class_group').distinct().order_by('-created_at')

    return render(request, 'web/student/materials.html', {
        'student': student,
        'materials': materials_qs,
    })
