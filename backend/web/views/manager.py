from datetime import timedelta

from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Attendance, Classe, ClassGroup, Schedule
from centers.models import ClassRoom, Subject
from people.models import Student, StudentRequest, Teacher
from quizzes.models import Quiz

from ..decorators import manager_required
from ..forms import (
    ClasseForm,
    ClassGroupForm,
    ClassroomForm,
    ScheduleForm,
    StudentForm,
    SubjectForm,
    TeacherForm,
)
from ..services import (
    create_student_by_manager,
    create_teacher_by_manager,
    reset_student_password,
    reset_teacher_password,
)
from ..utils import (
    group_students,
    manager_center,
    parse_date,
    save_attendance,
    set_credentials,
)


def _center(request):
    center = manager_center(request.user)
    if center is None:
        messages.error(request, "Aucun centre n'est associé à votre compte.")
    return center


def _get_teacher(request, center, pk):
    return get_object_or_404(Teacher, pk=pk, center=center)


def _get_student(request, center, pk):
    return get_object_or_404(Student, pk=pk, center=center)


@manager_required
def dashboard(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    today = timezone.localdate()
    last_month = timezone.now() - timedelta(days=30)

    total_attendance = Attendance.objects.filter(
        class_group__center=center, date__gte=last_month,
    ).count()
    present_count = Attendance.objects.filter(
        class_group__center=center, date__gte=last_month, status='present',
    ).count()
    attendance_rate = round(present_count / total_attendance * 100, 1) if total_attendance else 0

    context = {
        'center': center,
        'today': today,
        'total_teachers': Teacher.objects.filter(center=center, is_active=True).count(),
        'pending_teachers': Teacher.objects.filter(center=center, is_active=False).count(),
        'total_students': Student.objects.filter(center=center, status='approved').count(),
        'total_students_all': Student.objects.filter(center=center).count(),
        'total_classrooms': ClassRoom.objects.filter(center=center, is_active=True).count(),
        'total_classes': Classe.objects.filter(center=center).count(),
        'total_groups': ClassGroup.objects.filter(center=center).count(),
        'total_quizzes': Quiz.objects.filter(teacher__center=center).count(),
        'pending_requests': StudentRequest.objects.filter(center=center, status='pending').count(),
        'sessions_today': Schedule.objects.filter(
            center=center, day_of_week=today.weekday(), status='active',
        ).select_related('class_group', 'classroom', 'teacher__user').order_by('start_time'),
        'attendance_rate': attendance_rate,
        'recent_students': Student.objects.filter(center=center).select_related(
            'classe', 'class_group',
        )[:5],
        'recent_requests': StudentRequest.objects.filter(
            center=center, status='pending',
        ).select_related('student')[:5],
    }
    return render(request, 'web/manager/dashboard.html', context)


@manager_required
def teachers(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    qs = Teacher.objects.filter(center=center).select_related('user').annotate(
        classes_count=Count('class_groups'),
    ).order_by('-created_at')
    if search:
        qs = qs.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__email__icontains=search)
            | Q(speciality__icontains=search)
        )
    if status == 'pending':
        qs = qs.filter(is_active=False)
    elif status == 'active':
        qs = qs.filter(is_active=True)

    return render(request, 'web/manager/teachers.html', {
        'center': center,
        'teachers': qs,
        'search': search,
        'status': status,
        'pending_count': Teacher.objects.filter(center=center, is_active=False).count(),
    })


@manager_required
def teacher_create(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    if request.method == 'POST':
        form = TeacherForm(request.POST, center=center)
        if form.is_valid():
            teacher, password, email_sent = create_teacher_by_manager(center, form.cleaned_data)
            set_credentials(
                request,
                "Compte enseignant créé",
                teacher.user.email or teacher.user.username,
                password,
                "Un email contenant les identifiants a été envoyé."
                if email_sent else "L'email n'a pas pu être envoyé : transmettez les identifiants manuellement.",
            )
            messages.success(request, f"Enseignant {teacher.user.get_full_name()} créé.")
            return redirect('web:manager_teachers')
    else:
        form = TeacherForm(center=center)

    return render(request, 'web/manager/teacher_form.html', {
        'form': form,
        'center': center,
        'title': 'Ajouter un enseignant',
    })


@manager_required
def teacher_edit(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    teacher = _get_teacher(request, center, pk)

    if request.method == 'POST':
        form = TeacherForm(request.POST, center=center, teacher=teacher)
        if form.is_valid():
            data = form.cleaned_data
            user = teacher.user
            user.first_name = data['first_name']
            user.last_name = data['last_name']
            user.email = data['email']
            user.username = data['email']
            user.phone = data.get('phone', '')
            user.save()
            teacher.speciality = data.get('speciality', '')
            teacher.save()
            teacher.classrooms.set(data.get('classrooms') or [])
            messages.success(request, "Enseignant mis à jour.")
            return redirect('web:manager_teachers')
    else:
        form = TeacherForm(center=center, teacher=teacher, initial={
            'first_name': teacher.user.first_name,
            'last_name': teacher.user.last_name,
            'email': teacher.user.email or teacher.user.username,
            'phone': teacher.user.phone,
            'speciality': teacher.speciality,
            'classrooms': teacher.classrooms.all(),
        })

    return render(request, 'web/manager/teacher_form.html', {
        'form': form,
        'center': center,
        'teacher': teacher,
        'title': 'Modifier un enseignant',
    })


@manager_required
def teacher_delete(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    teacher = _get_teacher(request, center, pk)
    if request.method == 'POST':
        name = teacher.user.get_full_name() or teacher.user.username
        user = teacher.user
        user.delete()
        messages.success(request, f"Enseignant {name} supprimé.")
        return redirect('web:manager_teachers')
    return render(request, 'web/confirm_delete.html', {
        'title': 'Supprimer un enseignant',
        'object': teacher,
        'warning': "Cette action supprime également le compte utilisateur et les quiz créés par cet enseignant.",
        'cancel_url': 'web:manager_teachers',
    })


@manager_required
@require_POST
def teacher_status(request, pk, action):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    teacher = _get_teacher(request, center, pk)
    active = action == 'approve'
    teacher.is_active = active
    teacher.save(update_fields=['is_active'])
    teacher.user.is_active = active
    teacher.user.save(update_fields=['is_active'])
    messages.success(
        request,
        "Enseignant approuvé." if active else "Enseignant rejeté / désactivé.",
    )
    return redirect('web:manager_teachers')


@manager_required
@require_POST
def teacher_reset_password(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    teacher = _get_teacher(request, center, pk)
    password = reset_teacher_password(teacher)
    set_credentials(
        request, "Nouveau mot de passe enseignant",
        teacher.user.email or teacher.user.username, password,
    )
    messages.success(request, "Mot de passe réinitialisé.")
    return redirect('web:manager_teachers')


@manager_required
def students(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    classe_id = request.GET.get('classe', '')
    qs = Student.objects.filter(center=center).select_related(
        'user', 'classe', 'class_group',
    ).order_by('-created_at')
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(parent_phone__icontains=search)
            | Q(user__email__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    if classe_id:
        qs = qs.filter(classe_id=classe_id)

    return render(request, 'web/manager/students.html', {
        'center': center,
        'students': qs,
        'classes': Classe.objects.filter(center=center),
        'search': search,
        'status': status,
        'classe_id': classe_id,
        'status_choices': Student.STATUS_CHOICES,
        'pending_count': Student.objects.filter(center=center, status='pending').count(),
        'approved_count': Student.objects.filter(center=center, status='approved').count(),
        'suspended_count': Student.objects.filter(center=center, status='suspended').count(),
        'rejected_count': Student.objects.filter(center=center, status='rejected').count(),
    })


@manager_required
def student_create(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    if request.method == 'POST':
        form = StudentForm(request.POST, center=center)
        if form.is_valid():
            student, password, login_id, result = create_student_by_manager(
                center, form.cleaned_data,
            )
            extra = "Un email contenant les identifiants a été envoyé." if result['email_sent'] else \
                "L'email n'a pas pu être envoyé : transmettez les identifiants manuellement."
            set_credentials(request, "Compte élève créé", login_id, password, extra)
            messages.success(request, f"Élève {student.first_name} {student.last_name} créé.")
            return redirect('web:manager_students')
    else:
        form = StudentForm(center=center, initial={'status': 'approved'})

    return render(request, 'web/manager/student_form.html', {
        'form': form,
        'center': center,
        'title': 'Inscrire un élève',
    })


@manager_required
def student_edit(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    student = _get_student(request, center, pk)

    if request.method == 'POST':
        form = StudentForm(request.POST, center=center, student=student)
        if form.is_valid():
            data = form.cleaned_data
            student.first_name = data['first_name']
            student.last_name = data['last_name']
            student.phone = data.get('phone', '')
            student.parent_phone = data.get('parent_phone', '')
            student.date_of_birth = data.get('date_of_birth')
            student.classe = data.get('classe')
            student.class_group = data.get('class_group')
            student.status = data['status']
            student.save()
            if student.user_id:
                user = student.user
                user.first_name = data['first_name']
                user.last_name = data['last_name']
                user.phone = data.get('phone', '')
                if data.get('email'):
                    user.email = data['email']
                user.is_active = data['status'] == 'approved'
                user.save()
            messages.success(request, "Élève mis à jour.")
            return redirect('web:manager_students')
    else:
        form = StudentForm(center=center, student=student, initial={
            'first_name': student.first_name,
            'last_name': student.last_name,
            'email': student.user.email if student.user_id else '',
            'phone': student.phone,
            'parent_phone': student.parent_phone,
            'date_of_birth': student.date_of_birth,
            'classe': student.classe,
            'class_group': student.class_group,
            'status': student.status,
        })

    return render(request, 'web/manager/student_form.html', {
        'form': form,
        'center': center,
        'student': student,
        'title': 'Modifier un élève',
    })


@manager_required
def student_delete(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    student = _get_student(request, center, pk)
    if request.method == 'POST':
        name = f"{student.first_name} {student.last_name}"
        if student.user_id:
            student.user.delete()
        else:
            student.delete()
        messages.success(request, f"Élève {name} supprimé.")
        return redirect('web:manager_students')
    return render(request, 'web/confirm_delete.html', {
        'title': 'Supprimer un élève',
        'object': student,
        'warning': "Cette action supprime également le compte utilisateur, les résultats de quiz et les présences de cet élève.",
        'cancel_url': 'web:manager_students',
    })


@manager_required
@require_POST
def student_status(request, pk, action):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    student = _get_student(request, center, pk)
    mapping = {
        'approve': 'approved',
        'suspend': 'suspended',
        'reject': 'rejected',
        'pending': 'pending',
    }
    if action not in mapping:
        messages.error(request, "Action inconnue.")
        return redirect('web:manager_students')

    student.status = mapping[action]
    student.save(update_fields=['status'])
    if student.user_id:
        student.user.is_active = student.status == 'approved'
        student.user.save(update_fields=['is_active'])
    if action == 'approve':
        student.requests.filter(status='pending').update(
            status='approved', processed_at=timezone.now(),
        )
    elif action == 'reject':
        student.requests.filter(status='pending').update(
            status='rejected', processed_at=timezone.now(),
        )
    elif action == 'suspend':
        student.requests.filter(status='pending').update(
            status='suspended', processed_at=timezone.now(),
        )
    messages.success(request, f"Statut de l'élève mis à jour : {student.get_status_display()}.")
    return redirect('web:manager_students')


@manager_required
@require_POST
def student_reset_password(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    student = _get_student(request, center, pk)
    password = reset_student_password(student)
    if password is None:
        messages.error(request, "Cet élève n'a pas de compte utilisateur.")
    else:
        login_id = student.user.email or student.user.username
        set_credentials(request, "Nouveau mot de passe élève", login_id, password)
        messages.success(request, "Mot de passe réinitialisé.")
    return redirect('web:manager_students')


@manager_required
def subjects(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.center = center
            subject.save()
            messages.success(request, f"Matière « {subject.name} » ajoutée.")
            return redirect('web:manager_subjects')
    else:
        form = SubjectForm()

    return render(request, 'web/manager/subjects.html', {
        'center': center,
        'subjects': Subject.objects.filter(center=center).annotate(
            groups_count=Count('class_groups'),
        ),
        'form': form,
    })


@manager_required
def subject_edit(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    subject = get_object_or_404(Subject, pk=pk, center=center)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, "Matière mise à jour.")
            return redirect('web:manager_subjects')
    else:
        form = SubjectForm(instance=subject)
    return render(request, 'web/manager/object_form.html', {
        'form': form,
        'title': 'Modifier une matière',
        'cancel_url': 'web:manager_subjects',
    })


@manager_required
def subject_delete(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    subject = get_object_or_404(Subject, pk=pk, center=center)
    if request.method == 'POST':
        subject.delete()
        messages.success(request, "Matière supprimée.")
        return redirect('web:manager_subjects')
    return render(request, 'web/confirm_delete.html', {
        'title': 'Supprimer une matière',
        'object': subject,
        'warning': "Les groupes de classe liés à cette matière seront également supprimés.",
        'cancel_url': 'web:manager_subjects',
    })


@manager_required
def classrooms(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    if request.method == 'POST':
        form = ClassroomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.center = center
            room.save()
            messages.success(request, f"Salle « {room.name} » ajoutée.")
            return redirect('web:manager_classrooms')
    else:
        form = ClassroomForm()

    return render(request, 'web/manager/classrooms.html', {
        'center': center,
        'classrooms': ClassRoom.objects.filter(center=center).annotate(
            groups_count=Count('groups'), teachers_count=Count('teachers'),
        ),
        'form': form,
    })


@manager_required
def classroom_edit(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    room = get_object_or_404(ClassRoom, pk=pk, center=center)
    if request.method == 'POST':
        form = ClassroomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, "Salle mise à jour.")
            return redirect('web:manager_classrooms')
    else:
        form = ClassroomForm(instance=room)
    return render(request, 'web/manager/object_form.html', {
        'form': form,
        'title': 'Modifier une salle',
        'cancel_url': 'web:manager_classrooms',
    })


@manager_required
def classroom_delete(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    room = get_object_or_404(ClassRoom, pk=pk, center=center)
    if request.method == 'POST':
        room.delete()
        messages.success(request, "Salle supprimée.")
        return redirect('web:manager_classrooms')
    return render(request, 'web/confirm_delete.html', {
        'title': 'Supprimer une salle',
        'object': room,
        'warning': "Les groupes de classe utilisant cette salle seront détachés.",
        'cancel_url': 'web:manager_classrooms',
    })


@manager_required
def classes(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    if request.method == 'POST':
        form = ClasseForm(request.POST)
        if form.is_valid():
            classe = form.save(commit=False)
            classe.center = center
            classe.save()
            messages.success(request, f"Classe « {classe.name} » créée.")
            return redirect('web:manager_classes')
    else:
        form = ClasseForm()

    return render(request, 'web/manager/classes.html', {
        'center': center,
        'classes': Classe.objects.filter(center=center).annotate(
            groups_count=Count('class_groups'),
            approved_students=Count('students', filter=Q(students__status='approved')),
        ),
        'form': form,
    })


@manager_required
def classe_detail(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    classe = get_object_or_404(Classe, pk=pk, center=center)
    return render(request, 'web/manager/classe_detail.html', {
        'center': center,
        'classe': classe,
        'groups': classe.class_groups.select_related('subject', 'teacher__user', 'classroom'),
        'students': Student.objects.filter(classe=classe).select_related('user', 'class_group'),
        'available_students': Student.objects.filter(
            center=center, status='approved', classe__isnull=True,
        ).select_related('user'),
    })


@manager_required
def classe_edit(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    classe = get_object_or_404(Classe, pk=pk, center=center)
    if request.method == 'POST':
        form = ClasseForm(request.POST, instance=classe)
        if form.is_valid():
            form.save()
            messages.success(request, "Classe mise à jour.")
            return redirect('web:manager_classe_detail', pk=classe.pk)
    else:
        form = ClasseForm(instance=classe)
    return render(request, 'web/manager/object_form.html', {
        'form': form,
        'title': 'Modifier une classe',
        'cancel_url': 'web:manager_classe_detail',
        'cancel_pk': classe.pk,
    })


@manager_required
def classe_delete(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    classe = get_object_or_404(Classe, pk=pk, center=center)
    if request.method == 'POST':
        classe.delete()
        messages.success(request, "Classe supprimée.")
        return redirect('web:manager_classes')
    return render(request, 'web/confirm_delete.html', {
        'title': 'Supprimer une classe',
        'object': classe,
        'warning': "Les groupes, emplois du temps et présences liés seront supprimés.",
        'cancel_url': 'web:manager_classes',
    })


@manager_required
def groups(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    groups_qs = ClassGroup.objects.filter(center=center).select_related(
        'classe', 'subject', 'teacher__user', 'classroom',
    ).annotate(students_total=Count('students'))
    return render(request, 'web/manager/groups.html', {
        'center': center,
        'groups': groups_qs,
    })


@manager_required
def group_create(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    if request.method == 'POST':
        form = ClassGroupForm(request.POST, center=center)
        if form.is_valid():
            try:
                group = form.save(commit=False)
                group.center = center
                group.save()
                messages.success(request, f"Groupe « {group.name} » créé.")
                return redirect('web:manager_group_detail', pk=group.pk)
            except IntegrityError:
                form.add_error(
                    None,
                    "Cette classe possède déjà un groupe pour cette matière.",
                )
    else:
        form = ClassGroupForm(center=center)

    return render(request, 'web/manager/group_form.html', {
        'form': form,
        'center': center,
        'title': 'Créer un groupe de classe',
    })


@manager_required
def group_detail(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    group = get_object_or_404(ClassGroup, pk=pk, center=center)
    students_qs = group_students(group)
    return render(request, 'web/manager/group_detail.html', {
        'center': center,
        'group': group,
        'students': students_qs,
        'schedules': group.schedules.select_related('classroom').order_by('day_of_week', 'start_time'),
        'quizzes': group.quizzes.select_related('teacher__user'),
        'materials': group.materials.select_related('subject', 'teacher__user'),
        'available_students': Student.objects.filter(
            center=center, status='approved',
        ).exclude(pk__in=students_qs.values('pk')).select_related('user'),
    })


@manager_required
def group_edit(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    group = get_object_or_404(ClassGroup, pk=pk, center=center)

    if request.method == 'POST':
        form = ClassGroupForm(request.POST, center=center, instance=group)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Groupe mis à jour.")
                return redirect('web:manager_group_detail', pk=group.pk)
            except IntegrityError:
                form.add_error(
                    None,
                    "Cette classe possède déjà un groupe pour cette matière.",
                )
    else:
        form = ClassGroupForm(center=center, instance=group)

    return render(request, 'web/manager/group_form.html', {
        'form': form,
        'center': center,
        'group': group,
        'title': 'Modifier un groupe de classe',
    })


@manager_required
def group_delete(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    group = get_object_or_404(ClassGroup, pk=pk, center=center)
    if request.method == 'POST':
        group.delete()
        messages.success(request, "Groupe supprimé.")
        return redirect('web:manager_groups')
    return render(request, 'web/confirm_delete.html', {
        'title': 'Supprimer un groupe',
        'object': group,
        'warning': "Les emplois du temps, présences et quiz liés à ce groupe seront supprimés.",
        'cancel_url': 'web:manager_groups',
    })


@manager_required
def group_add_student(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    group = get_object_or_404(ClassGroup, pk=pk, center=center)
    if request.method != 'POST':
        return redirect('web:manager_group_detail', pk=group.pk)

    student = Student.objects.filter(pk=request.POST.get('student_id'), center=center).first()
    if student is None:
        messages.error(request, "Élève introuvable dans ce centre.")
    else:
        student.class_group = group
        if group.classe_id:
            student.classe = group.classe
        student.save()
        messages.success(request, f"{student.first_name} {student.last_name} ajouté au groupe.")
    return redirect('web:manager_group_detail', pk=group.pk)


@manager_required
def group_remove_student(request, pk, student_id):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    group = get_object_or_404(ClassGroup, pk=pk, center=center)
    if request.method == 'POST':
        student = Student.objects.filter(pk=student_id, center=center).first()
        if student:
            if group.classe_id and student.classe_id == group.classe_id:
                student.classe = None
            if student.class_group_id == group.pk:
                student.class_group = None
            student.save()
            messages.success(request, "Élève retiré du groupe.")
    return redirect('web:manager_group_detail', pk=group.pk)


@manager_required
def requests_view(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    status = request.GET.get('status', 'pending')
    qs = StudentRequest.objects.filter(center=center).select_related(
        'student', 'student__user', 'student__classe', 'student__class_group',
    ).order_by('-created_at')
    if status:
        qs = qs.filter(status=status)

    return render(request, 'web/manager/requests.html', {
        'center': center,
        'requests': qs,
        'status': status,
        'status_choices': StudentRequest.STATUS_CHOICES,
        'pending_count': StudentRequest.objects.filter(center=center, status='pending').count(),
    })


@manager_required
def request_process(request, pk, action):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    student_request = get_object_or_404(StudentRequest, pk=pk, center=center)
    if action not in ('approve', 'suspend', 'reject'):
        messages.error(request, "Action inconnue.")
        return redirect('web:manager_requests')

    if request.method == 'POST':
        mapping = {'approve': 'approved', 'suspend': 'suspended', 'reject': 'rejected'}
        student_request.status = mapping[action]
        student_request.processed_at = timezone.now()
        message = request.POST.get('message', '').strip()
        if message:
            student_request.message = message
        student_request.save()

        student = student_request.student
        student.status = mapping[action]
        if action == 'approve' and not student.center_id:
            student.center = center
        student.save()
        if student.user_id:
            student.user.is_active = action == 'approve'
            student.user.save(update_fields=['is_active'])

        messages.success(request, f"Demande {student_request.get_status_display().lower()}.")
        return redirect('web:manager_requests')

    return render(request, 'web/manager/request_process.html', {
        'center': center,
        'request_obj': student_request,
        'action': action,
    })


@manager_required
def schedule(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    schedules = Schedule.objects.filter(center=center).select_related(
        'class_group', 'classroom', 'teacher__user', 'class_group__subject',
    ).order_by('day_of_week', 'start_time')
    grouped = {day: [] for day, _ in Schedule.DAY_CHOICES}
    for item in schedules:
        grouped[item.day_of_week].append(item)

    return render(request, 'web/manager/schedule.html', {
        'center': center,
        'week': [(label, grouped[value]) for value, label in Schedule.DAY_CHOICES],
        'total': schedules.count(),
        'today_weekday': timezone.localdate().weekday(),
    })


def _schedule_conflicts(center, form, exclude_pk=None):
    data = form.cleaned_data
    group = data.get('class_group')
    room = data.get('classroom')
    day = data.get('day_of_week')
    start = data.get('start_time')
    end = data.get('end_time')
    if not (day is not None and start and end):
        return False

    conflicts = Schedule.objects.filter(
        center=center, day_of_week=day,
        start_time__lt=end, end_time__gt=start,
    )
    if exclude_pk:
        conflicts = conflicts.exclude(pk=exclude_pk)
    conflict = conflicts.filter(
        Q(class_group=group) | Q(classroom=room) if room else Q(class_group=group)
    ).first()
    if conflict is not None:
        form.add_error(None, f"Conflit avec « {conflict} » sur ce créneau.")
        return True
    return False


@manager_required
def schedule_create(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    if request.method == 'POST':
        form = ScheduleForm(request.POST, center=center)
        if form.is_valid() and not _schedule_conflicts(center, form):
            item = form.save(commit=False)
            item.center = center
            if not item.teacher_id and item.class_group_id:
                item.teacher = item.class_group.teacher
            item.save()
            messages.success(request, "Créneau ajouté à l'emploi du temps.")
            return redirect('web:manager_schedule')
    else:
        form = ScheduleForm(center=center)

    return render(request, 'web/manager/schedule_form.html', {
        'form': form,
        'center': center,
        'title': 'Ajouter un créneau',
    })


@manager_required
def schedule_edit(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    item = get_object_or_404(Schedule, pk=pk, center=center)

    if request.method == 'POST':
        form = ScheduleForm(request.POST, center=center, instance=item)
        if form.is_valid() and not _schedule_conflicts(center, form, exclude_pk=item.pk):
            schedule_obj = form.save(commit=False)
            schedule_obj.center = center
            schedule_obj.save()
            messages.success(request, "Créneau mis à jour.")
            return redirect('web:manager_schedule')
    else:
        form = ScheduleForm(center=center, instance=item)

    return render(request, 'web/manager/schedule_form.html', {
        'form': form,
        'center': center,
        'item': item,
        'title': 'Modifier un créneau',
    })


@manager_required
def schedule_delete(request, pk):
    center = _center(request)
    if center is None:
        return redirect('web:home')
    item = get_object_or_404(Schedule, pk=pk, center=center)
    if request.method == 'POST':
        item.delete()
        messages.success(request, "Créneau supprimé.")
        return redirect('web:manager_schedule')
    return render(request, 'web/confirm_delete.html', {
        'title': 'Supprimer un créneau',
        'object': item,
        'cancel_url': 'web:manager_schedule',
    })


@manager_required
def attendance(request):
    center = _center(request)
    if center is None:
        return redirect('web:home')

    groups_qs = ClassGroup.objects.filter(center=center).select_related('classe', 'subject')
    group = None
    selected_date = timezone.localdate()

    if request.method == 'POST':
        group = groups_qs.filter(pk=request.POST.get('group')).first()
        if group is None:
            messages.error(request, "Groupe de classe introuvable.")
            return redirect('web:manager_attendance')
        selected_date = save_attendance(request, group)
        return redirect(
            f"/manager/attendance/?group={group.pk}&date={selected_date.isoformat()}"
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
            for item in Attendance.objects.filter(
                class_group=group, date=selected_date,
            )
        }

    return render(request, 'web/manager/attendance.html', {
        'center': center,
        'groups': groups_qs,
        'group': group,
        'selected_date': selected_date,
        'students': students_qs,
        'existing': existing,
        'status_choices': Attendance.STATUS_CHOICES,
        'today': timezone.localdate(),
    })
