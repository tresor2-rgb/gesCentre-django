from django.db import models


class Center(models.Model):
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='centers/logos/', blank=True, null=True)
    manager = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, related_name='managed_center', null=True, blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Subject(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name='subjects')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ClassRoom(models.Model):
    name = models.CharField(max_length=100)
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name='classrooms')
    capacity = models.PositiveIntegerField(default=30)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.center.name})"

    @property
    def groups_using_count(self):
        return self.groups.count()
