from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Attendance, ClassGroup, Schedule
from people.models import Student
from quizzes.models import Quiz, QuizOption, QuizQuestion, QuizResult

from ..decorators import teacher_required
from ..forms import MaterialForm, QuestionForm, QuizForm, ScheduleForm
from ..services import mark_results_read
from ..utils import (
    group_students,
    parse_date,
    save_attendance,
    teacher_groups,
)

from materials.models import SubjectMaterial


def _teacher(request):
    return getattr(request.user, 'teacher_profile', None)


def _get_group(request, pk):
    teacher = _teacher(request)
    return get_object_or_404(ClassGroup, pk=pk, teacher=teacher)


def _get_quiz(request, pk):
    teacher = _teacher(request)
    return get_object_or_404(Quiz, pk=pk, teacher=teacher)


@teacher_required
def dashboard(request):
    teacher = _teacher(request)
    if teacher is None:
        messages.error(request, "Profil enseignant introuvable.")
        return redirect('web:home')

    today = timezone.localdate()
    groups = teacher_groups(teacher)
    students_count = 0
    for group in groups:
        students_count += group_students(group).count()

    recent_results = QuizResult.objects.filter(
        quiz__teacher=teacher,
    ).select_related('student', 'quiz').order_by('-completed_at')[:8]

    context = {
        'teacher': teacher,
        'center': teacher.center,
        'today': today,
        'groups_count': groups.count(),
        'students_count': students_count,
        'quizzes_count': Quiz.objects.filter(teacher=teacher).count(),
        'active_quizzes': Quiz.objects.filter(teacher=teacher, is_active=True).count(),
        'materials_count': SubjectMaterial.objects.filter(teacher=teacher).count(),
        'unread_results': QuizResult.objects.filter(
            quiz__teacher=teacher, is_read_by_teacher=False,
        ).count(),
        'sessions_today': Schedule.objects.filter(
            Q(teacher=teacher) | Q(class_group__teacher=teacher),
            day_of_week=today.weekday(), status='active',
        ).select_related('class_group', 'classroom').distinct().order_by('start_time'),
        'groups': groups[:6],
        'recent_results': recent_results,
    }
    return render(request, 'web/teacher/dashboard.html', context)


@teacher_required
def classes(request):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    return render(request, 'web/teacher/classes.html', {
        'teacher': teacher,
        'groups': teacher_groups(teacher),
    })


@teacher_required
def class_detail(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    group = _get_group(request, pk)
    return render(request, 'web/teacher/class_detail.html', {
        'teacher': teacher,
        'group': group,
        'students': group_students(group),
        'schedules': group.schedules.select_related('classroom').order_by('day_of_week', 'start_time'),
        'quizzes': group.quizzes.filter(teacher=teacher),
        'materials': group.materials.filter(teacher=teacher),
    })


@teacher_required
def schedule(request):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')

    items = Schedule.objects.filter(
        Q(teacher=teacher) | Q(class_group__teacher=teacher),
    ).select_related('class_group', 'classroom').distinct().order_by('day_of_week', 'start_time')
    grouped = {day: [] for day, _ in Schedule.DAY_CHOICES}
    for item in items:
        grouped[item.day_of_week].append(item)

    return render(request, 'web/teacher/schedule.html', {
        'teacher': teacher,
        'week': [(label, grouped[value]) for value, label in Schedule.DAY_CHOICES],
        'total': items.count(),
        'today_weekday': timezone.localdate().weekday(),
    })


@teacher_required
def schedule_create(request):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')

    if request.method == 'POST':
        form = ScheduleForm(request.POST, center=teacher.center, teacher=teacher)
        if form.is_valid():
            item = form.save(commit=False)
            item.center = teacher.center
            item.teacher = teacher
            item.save()
            messages.success(request, "Créneau ajouté à votre emploi du temps.")
            return redirect('web:teacher_schedule')
    else:
        form = ScheduleForm(center=teacher.center, teacher=teacher)

    return render(request, 'web/teacher/schedule_form.html', {
        'form': form,
        'teacher': teacher,
        'title': 'Ajouter un créneau',
    })


@teacher_required
def schedule_edit(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    item = get_object_or_404(
        Schedule, pk=pk,
    )
    if item.teacher_id != teacher.pk and item.class_group and item.class_group.teacher_id != teacher.pk:
        messages.error(request, "Vous ne pouvez pas modifier ce créneau.")
        return redirect('web:teacher_schedule')

    if request.method == 'POST':
        form = ScheduleForm(request.POST, center=teacher.center, teacher=teacher, instance=item)
        if form.is_valid():
            schedule_obj = form.save(commit=False)
            schedule_obj.center = teacher.center
            schedule_obj.teacher = teacher
            schedule_obj.save()
            messages.success(request, "Créneau mis à jour.")
            return redirect('web:teacher_schedule')
    else:
        form = ScheduleForm(center=teacher.center, teacher=teacher, instance=item)

    return render(request, 'web/teacher/schedule_form.html', {
        'form': form,
        'teacher': teacher,
        'item': item,
        'title': 'Modifier un créneau',
    })


@teacher_required
def schedule_delete(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    item = get_object_or_404(Schedule, pk=pk)
    if item.teacher_id != teacher.pk and item.class_group and item.class_group.teacher_id != teacher.pk:
        messages.error(request, "Vous ne pouvez pas supprimer ce créneau.")
        return redirect('web:teacher_schedule')
    if request.method == 'POST':
        item.delete()
        messages.success(request, "Créneau supprimé.")
        return redirect('web:teacher_schedule')
    return render(request, 'web/confirm_delete.html', {
        'title': 'Supprimer un créneau',
        'object': item,
        'cancel_url': 'web:teacher_schedule',
    })


@teacher_required
def attendance(request):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')

    groups_qs = teacher_groups(teacher)
    group = None
    selected_date = timezone.localdate()

    if request.method == 'POST':
        group = groups_qs.filter(pk=request.POST.get('group')).first()
        if group is None:
            messages.error(request, "Groupe de classe introuvable.")
            return redirect('web:teacher_attendance')
        selected_date = save_attendance(request, group)
        return redirect(
            f"/teacher/attendance/?group={group.pk}&date={selected_date.isoformat()}"
        )

    group_id = request.GET.get('group')
    if group_id:
        group = groups_qs.filter(pk=group_id).first()
    if group is None:
        group = groups_qs.first()
    selected_date = parse_date(request.GET.get('date'), selected_date)

    students_qs = group_students(group) if group else Student.objects.none()
    existing = {}
    if group:
        existing = {
            item.student_id: item
            for item in Attendance.objects.filter(class_group=group, date=selected_date)
        }

    return render(request, 'web/teacher/attendance.html', {
        'teacher': teacher,
        'groups': groups_qs,
        'group': group,
        'selected_date': selected_date,
        'students': students_qs,
        'existing': existing,
        'status_choices': Attendance.STATUS_CHOICES,
        'today': timezone.localdate(),
    })


@teacher_required
def quizzes(request):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    qs = Quiz.objects.filter(teacher=teacher).annotate(
        submissions_count=Count('results'),
    ).order_by('-created_at')
    return render(request, 'web/teacher/quizzes.html', {
        'teacher': teacher,
        'quizzes': qs,
    })


@teacher_required
def quiz_create(request):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')

    if request.method == 'POST':
        form = QuizForm(request.POST, teacher=teacher)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.teacher = teacher
            quiz.save()
            form.save_m2m()
            messages.success(
                request,
                "Quiz créé. Ajoutez maintenant les questions et les réponses.",
            )
            return redirect('web:teacher_quiz_detail', pk=quiz.pk)
    else:
        form = QuizForm(teacher=teacher)

    return render(request, 'web/teacher/quiz_form.html', {
        'form': form,
        'teacher': teacher,
        'title': 'Créer un quiz',
    })


@teacher_required
def quiz_detail(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    quiz = _get_quiz(request, pk)
    return render(request, 'web/teacher/quiz_detail.html', {
        'teacher': teacher,
        'quiz': quiz,
        'questions': quiz.questions.prefetch_related('options'),
        'results_count': quiz.results.count(),
        'question_form': QuestionForm(),
    })


@teacher_required
def quiz_edit(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    quiz = _get_quiz(request, pk)

    if request.method == 'POST':
        form = QuizForm(request.POST, teacher=teacher, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, "Quiz mis à jour.")
            return redirect('web:teacher_quiz_detail', pk=quiz.pk)
    else:
        form = QuizForm(teacher=teacher, instance=quiz)

    return render(request, 'web/teacher/quiz_form.html', {
        'form': form,
        'teacher': teacher,
        'quiz': quiz,
        'title': 'Modifier le quiz',
    })


@teacher_required
def quiz_delete(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    quiz = _get_quiz(request, pk)
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, "Quiz supprimé.")
        return redirect('web:teacher_quizzes')
    return render(request, 'web/confirm_delete.html', {
        'title': 'Supprimer un quiz',
        'object': quiz,
        'warning': "Les questions et les résultats des élèves seront définitivement supprimés.",
        'cancel_url': 'web:teacher_quizzes',
    })


@teacher_required
@require_POST
def quiz_toggle(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    quiz = _get_quiz(request, pk)
    if request.method == 'POST':
        quiz.is_active = not quiz.is_active
        quiz.save(update_fields=['is_active'])
        messages.success(
            request,
            "Quiz activé." if quiz.is_active else "Quiz désactivé.",
        )
    return redirect('web:teacher_quiz_detail', pk=quiz.pk)


@teacher_required
def quiz_add_question(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    quiz = _get_quiz(request, pk)

    if request.method != 'POST':
        return render(request, 'web/teacher/question_form.html', {
            'teacher': teacher,
            'quiz': quiz,
            'form': QuestionForm(),
        })

    form = QuestionForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "La question n'a pas pu être ajoutée. Vérifiez les champs.")
        return render(request, 'web/teacher/question_form.html', {
            'teacher': teacher,
            'quiz': quiz,
            'form': form,
        })

    question = form.save(commit=False)
    question.quiz = quiz
    if not question.order:
        question.order = quiz.questions.count() + 1
    question.save()

    qtype = form.cleaned_data['question_type']
    if qtype == 'qcm':
        count = int(request.POST.get('option_count', 0) or 0)
        correct = request.POST.get('correct_option', '')
        for index in range(count):
            text = request.POST.get(f'option_text_{index}', '').strip()
            image = request.FILES.get(f'option_image_{index}')
            if not text and not image:
                continue
            QuizOption.objects.create(
                question=question,
                option_text=text,
                image=image,
                is_correct=str(index) == correct,
            )
        if not question.options.filter(is_correct=True).exists() or question.options.count() < 2:
            question.delete()
            form.add_error(
                None,
                "Un QCM doit comporter au moins deux options et une bonne réponse.",
            )
            return render(request, 'web/teacher/question_form.html', {
                'teacher': teacher,
                'quiz': quiz,
                'form': form,
            })
    elif qtype == 'true_false':
        correct = request.POST.get('correct_option', '0')
        QuizOption.objects.create(
            question=question, option_text='Vrai', is_correct=correct == '0',
        )
        QuizOption.objects.create(
            question=question, option_text='Faux', is_correct=correct == '1',
        )
    else:
        answer = request.POST.get('answer_text', '').strip()
        if not answer:
            question.delete()
            form.add_error(None, "Indiquez la réponse correcte attendue.")
            return render(request, 'web/teacher/question_form.html', {
                'teacher': teacher,
                'quiz': quiz,
                'form': form,
            })
        QuizOption.objects.create(question=question, option_text=answer, is_correct=True)

    messages.success(request, "Question ajoutée.")
    return redirect('web:teacher_quiz_detail', pk=quiz.pk)


@teacher_required
def question_delete(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    question = get_object_or_404(QuizQuestion, pk=pk, quiz__teacher=teacher)
    quiz_pk = question.quiz_id
    if request.method == 'POST':
        question.delete()
        messages.success(request, "Question supprimée.")
    return redirect('web:teacher_quiz_detail', pk=quiz_pk)


@teacher_required
def quiz_results(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    quiz = _get_quiz(request, pk)
    results = list(quiz.results.select_related('student', 'student__user'))
    mark_results_read(results, quiz)
    return render(request, 'web/teacher/quiz_results.html', {
        'teacher': teacher,
        'quiz': quiz,
        'results': results,
    })


@teacher_required
def materials(request):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    return render(request, 'web/teacher/materials.html', {
        'teacher': teacher,
        'materials': SubjectMaterial.objects.filter(teacher=teacher).select_related(
            'subject', 'class_group',
        ),
    })


@teacher_required
def material_create(request):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')

    if request.method == 'POST':
        form = MaterialForm(
            request.POST, request.FILES, center=teacher.center, teacher=teacher,
        )
        if form.is_valid():
            material = form.save(commit=False)
            material.teacher = teacher
            material.center = teacher.center
            material.save()
            messages.success(request, "Support de cours ajouté.")
            return redirect('web:teacher_materials')
    else:
        form = MaterialForm(center=teacher.center, teacher=teacher)

    return render(request, 'web/teacher/material_form.html', {
        'form': form,
        'teacher': teacher,
        'title': 'Ajouter un support de cours',
    })


@teacher_required
def material_edit(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    material = get_object_or_404(SubjectMaterial, pk=pk, teacher=teacher)

    if request.method == 'POST':
        form = MaterialForm(
            request.POST, request.FILES, center=teacher.center,
            teacher=teacher, instance=material,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Support mis à jour.")
            return redirect('web:teacher_materials')
    else:
        form = MaterialForm(center=teacher.center, teacher=teacher, instance=material)

    return render(request, 'web/teacher/material_form.html', {
        'form': form,
        'teacher': teacher,
        'material': material,
        'title': 'Modifier un support de cours',
    })


@teacher_required
def material_delete(request, pk):
    teacher = _teacher(request)
    if teacher is None:
        return redirect('web:home')
    material = get_object_or_404(SubjectMaterial, pk=pk, teacher=teacher)
    if request.method == 'POST':
        material.delete()
        messages.success(request, "Support supprimé.")
        return redirect('web:teacher_materials')
    return render(request, 'web/confirm_delete.html', {
        'title': 'Supprimer un support',
        'object': material,
        'cancel_url': 'web:teacher_materials',
    })
