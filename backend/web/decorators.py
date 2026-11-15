from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(*roles):
    """Restreint une vue à un ou plusieurs rôles (les superusers passent toujours)."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser or request.user.role in roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "Vous n'avez pas accès à cette page.")
            return redirect('web:home')

        return wrapper

    return decorator


manager_required = role_required('manager')
teacher_required = role_required('teacher')
student_required = role_required('student')
