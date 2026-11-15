from django.db import models


class Classe(models.Model):
    name = models.CharField(max_length=100)
    center = models.ForeignKey('centers.Center', on_delete=models.CASCADE, related_name='classes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Classes'

    def __str__(self):
        return self.name

    @property
    def students_count(self):
        return self.students.filter(status='approved').count()

    @property
    def subjects_count(self):
        return self.class_groups.count()


class ClassGroup(models.Model):
    name = models.CharField(max_length=100, blank=True)
    classe = models.ForeignKey(
        Classe, on_delete=models.CASCADE,
        null=True, blank=True, related_name='class_groups',
    )
    subject = models.ForeignKey('centers.Subject', on_delete=models.CASCADE, related_name='class_groups')
    teacher = models.ForeignKey('people.Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='class_groups')
    classroom = models.ForeignKey('centers.ClassRoom', on_delete=models.SET_NULL, null=True, blank=True, related_name='groups')
    center = models.ForeignKey('centers.Center', on_delete=models.CASCADE, related_name='class_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Class Groups'
        constraints = [
            models.UniqueConstraint(
                fields=['classe', 'subject'],
                name='unique_subject_per_classe',
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.subject.name}"

    def save(self, *args, **kwargs):
        if not self.name and self.classe_id and self.subject_id:
            self.name = f"{self.classe.name} - {self.subject.name}"
        super().save(*args, **kwargs)

    @property
    def students_count(self):
        if self.classe_id:
            return self.classe.students_count
        return self.students.filter(status='approved').count()

    @property
    def schedule_info(self):
        schedules = self.schedules.all()
        return [
            {"day": s.get_day_of_week_display(), "start": str(s.start_time), "end": str(s.end_time)}
            for s in schedules
        ]


class Schedule(models.Model):
    DAY_CHOICES = (
        (0, 'Lundi'),
        (1, 'Mardi'),
        (2, 'Mercredi'),
        (3, 'Jeudi'),
        (4, 'Vendredi'),
        (5, 'Samedi'),
        (6, 'Dimanche'),
    )

    STATUS_CHOICES = (
        ('active', 'Actif'),
        ('cancelled', 'Annulé'),
        ('rescheduled', 'Reporté'),
    )

    # Core fields
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.CASCADE, related_name='schedules',
        null=True, blank=True,
    )
    classroom = models.ForeignKey(
        'centers.ClassRoom', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='schedules',
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    # Extended fields for frontend compatibility
    title = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField(blank=True, default='')
    color = models.CharField(max_length=20, blank=True, default='#3F51B5')
    center = models.ForeignKey(
        'centers.Center', on_delete=models.CASCADE,
        related_name='schedules', null=True, blank=True,
    )
    teacher = models.ForeignKey(
        'people.Teacher', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='schedules',
    )
    is_recurring = models.BooleanField(default=True)
    specific_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']
        verbose_name_plural = 'Schedules'

    def __str__(self):
        return f"{self.title or (self.class_group.name if self.class_group else 'Sans titre')} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

    def save(self, *args, **kwargs):
        # Auto-populate title, center, teacher from class_group if not set
        if self.class_group:
            if not self.title:
                self.title = self.class_group.name
            if not self.center_id:
                self.center = self.class_group.center
            if not self.teacher_id:
                self.teacher = self.class_group.teacher
            if not self.classroom_id:
                self.classroom = self.class_group.classroom
        super().save(*args, **kwargs)


class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('late', 'Retard'),
        ('excused', 'Excusé'),
    )

    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.CASCADE, related_name='attendances',
    )
    student = models.ForeignKey(
        'people.Student', on_delete=models.CASCADE, related_name='attendances',
    )
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    remarks = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'student']
        unique_together = ['class_group', 'student', 'date']

    def __str__(self):
        return f"{self.student} - {self.class_group} - {self.date} ({self.status})"
