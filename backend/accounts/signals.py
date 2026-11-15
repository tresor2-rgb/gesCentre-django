from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

User = get_user_model()


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """Signal infrastructure for post-user-creation logic.

    The centre is currently created inside the RegisterView to keep the
    transaction tightly coupled with the registration payload. This signal
    is kept as an extension point for future behaviour (e.g. sending a
    welcome email, provisioning defaults, etc.).
    """
    if created:
        # Future: send welcome email, create default centre settings, etc.
        pass
