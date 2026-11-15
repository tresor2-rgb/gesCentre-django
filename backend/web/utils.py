from datetime import date, datetime

from django.contrib import messages
from django.shortcuts import redirect

from academics.models import Attendance, ClassGroup
from centers.models import Center
from people.models import Student


def manager_center(user):
    center = get_center(user)
    if center is None and user.is_superuser:
        center = Center.objects.first()
    return center


def get_center(user):
    """Retourne le centre rattaché à l'utilisateur, quel que soit son rôle."""
    if not user.is_authenticated:
        return None
    if hasattr(user, 'managed_center'):
        return user.managed_center
    teacher = get_teacher(user)
    if teacher is not None:
        return teacher.center
    student = get_student(user)
    if student is not None:
        return student.center
    return None


def get_teacher(user):
    if not user.is_authenticated:
        return None
    return getattr(user, 'teacher_profile', None)


def get_student(user):
    if not user.is_authenticated:
        return None
    return getattr(user, 'student_profile', None)


def group_students(group):
    """Élèves approuvés rattachés à un groupe de classe."""
    if group.classe_id:
        return Student.objects.filter(
            classe=group.classe, status='approved',
        ).select_related('user')
    return group.students.filter(status='approved').select_related('user')


def teacher_groups(teacher):
    return ClassGroup.objects.filter(teacher=teacher).select_related(
        'classe', 'subject', 'classroom', 'center',
    )


def student_groups(student):
    groups = ClassGroup.objects.none()
    if student.class_group_id:
        groups = ClassGroup.objects.filter(pk=student.class_group_id)
    elif student.classe_id:
        groups = ClassGroup.objects.filter(classe=student.classe)
    return groups.select_related('subject', 'teacher__user', 'classroom')


def parse_date(value, default=None):
    if not value:
        return default
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return default


def save_attendance(request, group):
    """Enregistre la feuille de présence d'un groupe pour une date donnée."""
    student_ids = request.POST.getlist('student_ids')
    day = parse_date(request.POST.get('date'), date.today())
    if not student_ids:
        messages.warning(request, "Aucun élève à enregistrer pour ce groupe.")
        return day

    for raw_id in student_ids:
        student = group_students(group).filter(pk=raw_id).first()
        if student is None:
            continue
        status = request.POST.get(f'status_{student.pk}', 'present')
        remarks = request.POST.get(f'remarks_{student.pk}', '').strip()
        Attendance.objects.update_or_create(
            class_group=group,
            student=student,
            date=day,
            defaults={'status': status, 'remarks': remarks},
        )
    messages.success(request, f"Présences enregistrées pour le {day.strftime('%d/%m/%Y')}.")
    return day


def redirect_with_error(request, message, fallback='web:home'):
    messages.error(request, message)
    return redirect(fallback)


def set_credentials(request, title, login_id, password, extra=None):
    request.session['web_credentials'] = {
        'title': title,
        'login_id': login_id,
        'password': password,
        'extra': extra or '',
    }


def pop_credentials(request):
    return request.session.pop('web_credentials', None)
