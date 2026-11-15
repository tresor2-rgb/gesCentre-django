from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from people.models import Notification
from people.notifications import send_email_credentials

from ..forms import (
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    ManagerRegisterForm,
    ProfileForm,
    StudentRegisterForm,
    TeacherRegisterForm,
)
from ..services import (
    create_manager_account,
    create_student_registration,
    create_teacher_registration,
)
from ..utils import get_center, get_student, get_teacher


def dashboard_url(user):
    if hasattr(user, 'managed_center'):
        return reverse('web:manager_dashboard')
    if hasattr(user, 'teacher_profile'):
        return reverse('web:teacher_dashboard')
    if hasattr(user, 'student_profile'):
        return reverse('web:student_dashboard')
    if user.is_superuser:
        return reverse('web:manager_dashboard')
    return reverse('web:login')


def home(request):
    if not request.user.is_authenticated:
        return redirect('web:login')
    return redirect(dashboard_url(request.user))


def login_view(request):
    if request.user.is_authenticated:
        return redirect('web:home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data['identifier'].strip()
            password = form.cleaned_data['password']
            user = get_user_model().objects.filter(
                Q(email__iexact=identifier) | Q(username__iexact=identifier)
            ).first()
            if user is not None:
                teacher = getattr(user, 'teacher_profile', None)
                if not user.is_active:
                    messages.error(
                        request,
                        "Ce compte est désactivé ou en attente de validation par votre centre.",
                    )
                elif teacher is not None and not teacher.is_active:
                    messages.error(
                        request,
                        "Votre compte enseignant est en attente de validation par le "
                        "responsable du centre.",
                    )
                else:
                    authenticated = authenticate(
                        request, username=user.username, password=password,
                    )
                    if authenticated is not None:
                        login(request, authenticated)
                        next_url = request.GET.get('next')
                        if next_url and next_url.startswith('/'):
                            return redirect(next_url)
                        return redirect('web:home')
                    messages.error(request, "Identifiant ou mot de passe incorrect.")
            else:
                messages.error(request, "Identifiant ou mot de passe incorrect.")
    else:
        form = LoginForm()

    return render(request, 'web/auth/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "Vous avez été déconnecté.")
    return redirect('web:login')


def register_select(request):
    return render(request, 'web/auth/register_select.html')


def register_view(request, role):
    if role not in ('manager', 'teacher', 'student'):
        messages.error(request, "Type de compte inconnu.")
        return redirect('web:register_select')

    form_class = {
        'manager': ManagerRegisterForm,
        'teacher': TeacherRegisterForm,
        'student': StudentRegisterForm,
    }[role]

    if request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if role == 'manager':
                user, center = create_manager_account(data)
                messages.success(
                    request,
                    f"Centre « {center.name} » créé. Connectez-vous avec {user.email}.",
                )
                return redirect('web:login')
            if role == 'teacher':
                create_teacher_registration(data['center'], data, data['password'])
                messages.success(
                    request,
                    "Votre demande de compte enseignant a été envoyée. "
                    "Elle doit être validée par le responsable du centre avant "
                    "que vous puissiez vous connecter.",
                )
                return redirect('web:login')
            create_student_registration(data['center'], data, data['password'])
            messages.success(
                request,
                "Votre demande d'inscription a été envoyée au centre. "
                "Elle doit être approuvée avant l'accès aux cours.",
            )
            return redirect('web:login')
    else:
        form = form_class()

    return render(request, 'web/auth/register.html', {
        'form': form,
        'role': role,
        'role_label': {
            'manager': 'Responsable de centre',
            'teacher': 'Enseignant',
            'student': 'Élève',
        }[role],
    })


def forgot_password_view(request):
    temp_password = None
    email_sent = False
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip()
            user = get_user_model().objects.filter(
                Q(email__iexact=email) | Q(username__iexact=email),
                is_active=True,
            ).first()
            if user is None:
                messages.error(request, "Aucun compte actif trouvé avec cet identifiant.")
            else:
                from people.notifications import generate_temp_password

                temp_password = generate_temp_password(12)
                user.set_password(temp_password)
                user.save(update_fields=['password'])
                email_sent = send_email_credentials(
                    user.first_name, user.last_name, user.email or email,
                    temp_password, get_center(user).name if get_center(user) else '',
                )
                messages.success(
                    request,
                    "Un nouveau mot de passe a été généré. "
                    "Il est affiché ci-dessous et envoyé par email si possible.",
                )
    else:
        form = ForgotPasswordForm()

    return render(request, 'web/auth/forgot_password.html', {
        'form': form,
        'temp_password': temp_password,
        'email_sent': email_sent,
    })


@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, user=user)
        if form.is_valid():
            data = form.cleaned_data
            user.first_name = data['first_name']
            user.last_name = data['last_name']
            user.phone = data.get('phone', '')
            email = data['email'].strip().lower()
            if email != user.email:
                user.email = email
                user.username = email
            if data.get('avatar'):
                user.avatar = data['avatar']
            user.save()
            messages.success(request, "Profil mis à jour.")
            return redirect('web:profile')
    else:
        form = ProfileForm(user=user, initial={
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email or user.username,
            'phone': user.phone,
        })

    return render(request, 'web/profile.html', {
        'form': form,
        'teacher': get_teacher(user),
        'student': get_student(user),
        'center': get_center(user),
    })


@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.set_password(form.cleaned_data['new_password'])
            request.user.save(update_fields=['password'])
            messages.success(request, "Mot de passe modifié. Reconnectez-vous.")
            logout(request)
            return redirect('web:login')
    else:
        form = ChangePasswordForm(user=request.user)
    return render(request, 'web/change_password.html', {'form': form})


@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(recipient=request.user)
    return render(request, 'web/notifications.html', {
        'notifications': notifications,
    })


@login_required
def notification_read(request, pk):
    notification = Notification.objects.filter(recipient=request.user, pk=pk).first()
    if notification:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        if notification.link:
            return redirect(notification.link)
    return redirect('web:notifications')


@login_required
@require_POST
def notifications_read_all(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, "Toutes les notifications ont été marquées comme lues.")
    return redirect('web:notifications')
