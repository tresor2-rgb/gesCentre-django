from django.db import models


class Teacher(models.Model):
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='teacher_profile')
    speciality = models.CharField(max_length=100, blank=True)
    center = models.ForeignKey('centers.Center', on_delete=models.CASCADE, related_name='teachers')
    classrooms = models.ManyToManyField('centers.ClassRoom', blank=True, related_name='teachers')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.center.name}"

    @property
    def first_name(self):
        return self.user.first_name

    @property
    def last_name(self):
        return self.user.last_name


class Student(models.Model):
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('suspended', 'Suspendu'),
        ('rejected', 'Rejeté'),
    )
    REGISTRATION_CHOICES = (
        ('manual', 'Inscrit par le responsable'),
        ('self_request', 'Demande spontanée'),
    )

    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='student_profile', null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    center = models.ForeignKey('centers.Center', on_delete=models.CASCADE, related_name='students')
    registration_type = models.CharField(max_length=20, choices=REGISTRATION_CHOICES, default='manual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    class_group = models.ForeignKey(
        'academics.ClassGroup', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='students',
    )
    classe = models.ForeignKey(
        'academics.Classe', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='students',
    )
    class_name = models.CharField(max_length=50, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class StudentRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('suspended', 'Suspendu'),
        ('rejected', 'Rejeté'),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='requests')
    center = models.ForeignKey('centers.Center', on_delete=models.CASCADE, related_name='student_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student} -> {self.center} ({self.status})"


class Notification(models.Model):
    TYPE_CHOICES = (
        ('info', 'Information'),
        ('quiz_submission', 'Soumission de quiz'),
    )

    recipient = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='info')
    link = models.CharField(max_length=255, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient} - {self.title}"
