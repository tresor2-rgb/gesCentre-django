from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from people.models import Notification, Student, StudentRequest, Teacher
from people.notifications import (
    generate_temp_password,
    generate_username,
    notify_student_credentials,
    send_email_credentials,
)

User = get_user_model()


@transaction.atomic
def create_manager_account(data):
    email = data['email'].strip().lower()
    user = User.objects.create_user(
        username=email,
        email=email,
        password=data['password'],
        first_name=data['first_name'],
        last_name=data['last_name'],
        phone=data.get('phone', ''),
        role='manager',
        is_staff=True,
        is_superuser=True,
    )
    from centers.models import Center

    center = Center.objects.create(
        name=data['center_name'],
        address=data.get('center_address', ''),
        phone=data.get('center_phone', ''),
        email=email,
        manager=user,
    )
    return user, center


@transaction.atomic
def create_teacher_by_manager(center, data):
    email = data['email'].strip().lower()
    password = generate_temp_password()
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=data['first_name'],
        last_name=data['last_name'],
        phone=data.get('phone', ''),
        role='teacher',
        is_active=True,
    )
    teacher = Teacher.objects.create(
        user=user,
        center=center,
        speciality=data.get('speciality', ''),
        is_active=True,
    )
    classrooms = data.get('classrooms')
    if classrooms:
        teacher.classrooms.set(classrooms)

    email_sent = send_email_credentials(
        data['first_name'], data['last_name'], email, password, center.name,
    )
    return teacher, password, email_sent


@transaction.atomic
def create_teacher_registration(center, data, password):
    email = data['email'].strip().lower()
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=data['first_name'],
        last_name=data['last_name'],
        phone=data.get('phone', ''),
        role='teacher',
    )
    teacher = Teacher.objects.create(
        user=user,
        center=center,
        speciality=data.get('speciality', ''),
        is_active=False,
    )
    return teacher


@transaction.atomic
def create_student_by_manager(center, data):
    email = (data.get('email') or '').strip().lower()
    password = generate_temp_password()
    student = Student.objects.create(
        first_name=data['first_name'],
        last_name=data['last_name'],
        phone=data.get('phone', ''),
        parent_phone=data.get('parent_phone', ''),
        date_of_birth=data.get('date_of_birth'),
        center=center,
        classe=data.get('classe'),
        class_group=data.get('class_group'),
        status=data.get('status', 'approved'),
        registration_type='manual',
    )
    username = generate_username(student.first_name, student.last_name)
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=student.first_name,
        last_name=student.last_name,
        phone=student.phone or '',
        role='student',
        is_active=student.status == 'approved',
    )
    student.user = user
    student.save(update_fields=['user'])

    login_id = email or username
    result = notify_student_credentials(student, login_id, password, center.name)
    return student, password, login_id, result


@transaction.atomic
def create_student_registration(center, data, password):
    email = data['email'].strip().lower()
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=data['first_name'],
        last_name=data['last_name'],
        phone=data.get('phone', ''),
        role='student',
    )
    group = data.get('class_group')
    student = Student.objects.create(
        user=user,
        first_name=data['first_name'],
        last_name=data['last_name'],
        phone=data.get('phone', ''),
        parent_phone=data.get('parent_phone', ''),
        date_of_birth=data.get('date_of_birth'),
        center=center,
        classe=group.classe if group else None,
        class_group=group,
        status='pending',
        registration_type='self_request',
    )
    StudentRequest.objects.create(
        student=student,
        center=center,
        status='pending',
        message="Nouvelle demande d'inscription à valider.",
    )
    return student


def reset_student_password(student):
    if not student.user_id:
        return None
    password = generate_temp_password()
    student.user.set_password(password)
    student.user.is_active = True
    student.user.save(update_fields=['password', 'is_active'])
    return password


def reset_teacher_password(teacher):
    password = generate_temp_password()
    teacher.user.set_password(password)
    teacher.user.save(update_fields=['password'])
    return password


def notify_quiz_submission(result):
    quiz = result.quiz
    student = result.student
    if not quiz.teacher or not quiz.teacher.user:
        return
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
        link=f'/teacher/quizzes/{quiz.id}/',
    )


def mark_results_read(results, quiz):
    just_read = [r for r in results if not r.is_read_by_teacher]
    if not just_read:
        return []
    from quizzes.models import QuizResult

    QuizResult.objects.filter(pk__in=[r.pk for r in just_read]).update(is_read_by_teacher=True)
    for result in just_read:
        result.is_read_by_teacher = True
        if result.student.user_id:
            Notification.objects.create(
                recipient=result.student.user,
                title='Résultat de quiz consulté',
                message=(
                    f"Votre enseignant a consulté votre résultat au quiz "
                    f"« {quiz.title} » : {result.score}/{result.total_points} points."
                ),
                notification_type='info',
            )
    return just_read
