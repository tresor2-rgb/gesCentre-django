from people.models import Notification, Student, StudentRequest, Teacher
from quizzes.models import QuizResult

from .utils import get_center, get_student, get_teacher, pop_credentials


def app_context(request):
    user = request.user
    context = {
        'unread_notifications': 0,
        'user_center': None,
        'teacher_profile': None,
        'student_profile': None,
        'credentials': None,
        'nav_pending_students': 0,
        'nav_pending_teachers': 0,
        'nav_pending_requests': 0,
        'nav_unread_results': 0,
    }
    if not user.is_authenticated:
        return context

    context['unread_notifications'] = Notification.objects.filter(
        recipient=user, is_read=False,
    ).count()
    center = get_center(user)
    teacher = get_teacher(user)
    context['user_center'] = center
    context['teacher_profile'] = teacher
    context['student_profile'] = get_student(user)
    context['credentials'] = pop_credentials(request)

    if center is not None and (hasattr(user, 'managed_center') or user.is_superuser):
        context['nav_pending_students'] = Student.objects.filter(
            center=center, status='pending',
        ).count()
        context['nav_pending_teachers'] = Teacher.objects.filter(
            center=center, is_active=False,
        ).count()
        context['nav_pending_requests'] = StudentRequest.objects.filter(
            center=center, status='pending',
        ).count()
    elif teacher is not None:
        context['nav_unread_results'] = QuizResult.objects.filter(
            quiz__teacher=teacher, is_read_by_teacher=False,
        ).count()

    return context
