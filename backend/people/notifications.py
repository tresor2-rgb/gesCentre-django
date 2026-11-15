import string
import random
import logging
from urllib.parse import quote

from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_temp_password(length=10):
    chars = string.ascii_letters + string.digits + '!@#$%&*'
    return ''.join(random.choices(chars, k=length))


def generate_username(first_name, last_name):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    slug = f"{first_name.strip().lower()}.{last_name.strip().lower()}"
    slug = ''.join(c for c in slug if c.isalnum() or c == '.')
    slug = slug.strip('.')

    if not User.objects.filter(username=slug).exists():
        return slug

    for i in range(2, 100):
        candidate = f"{slug}{i}"
        if not User.objects.filter(username=candidate).exists():
            return candidate

    return f"{slug}{random.randint(1000, 9999)}"


def build_credentials_message(first_name, last_name, login_id, password, center_name=''):
    lines = [
        f'Bonjour {first_name} {last_name},',
        '',
        f'Votre compte a été créé sur AppCentre'
        f'{" - " + center_name if center_name else ""}.',
        '',
        'Voici vos identifiants de connexion :',
        '',
        f'Identifiant : {login_id}',
        f'Mot de passe : {password}',
        '',
        'Vous pourrez modifier votre mot de passe après connexion.',
        '',
        'Connectez-vous sur : https://appcentre.com/login',
    ]
    return '\n'.join(lines)


def send_email_credentials(first_name, last_name, email, password, center_name=''):
    subject = f'AppCentre - Vos identifiants de connexion'
    message = build_credentials_message(first_name, last_name, email, password, center_name)

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@appcentre.com',
            [email],
            fail_silently=False,
        )
        logger.info(f'Email sent to {email}')
        return True
    except Exception as e:
        logger.warning(f'Failed to send email to {email}: {e}')
        return False


def build_whatsapp_link(phone, first_name, last_name, email, password, center_name=''):
    clean_phone = ''.join(c for c in phone if c.isdigit() or c == '+')
    if clean_phone.startswith('00'):
        clean_phone = '+' + clean_phone[2:]
    elif clean_phone.startswith('0'):
        clean_phone = '+225' + clean_phone

    message = build_credentials_message(first_name, last_name, email, password, center_name)
    encoded = quote(message)
    return f'https://wa.me/{clean_phone}?text={encoded}'


def notify_student_credentials(student, email, password, center_name=''):
    results = {
        'email_sent': False,
        'whatsapp_link': None,
    }

    if email:
        results['email_sent'] = send_email_credentials(
            student.first_name, student.last_name, email, password, center_name
        )

    phone = getattr(student, 'phone', '') or ''
    if phone:
        results['whatsapp_link'] = build_whatsapp_link(
            phone, student.first_name, student.last_name, email, password, center_name
        )

    return results
