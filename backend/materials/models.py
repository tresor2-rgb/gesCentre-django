from django.db import models


class SubjectMaterial(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(
        'centers.Subject', on_delete=models.CASCADE, related_name='materials',
    )
    teacher = models.ForeignKey(
        'people.Teacher', on_delete=models.CASCADE, related_name='materials',
    )
    class_group = models.ForeignKey(
        'academics.ClassGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='materials',
    )
    center = models.ForeignKey(
        'centers.Center', on_delete=models.CASCADE, related_name='materials',
    )
    file = models.FileField(upload_to='materials/files/', blank=True, null=True)
    external_link = models.URLField(blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sujet'
        verbose_name_plural = 'Sujets'

    def __str__(self):
        return self.title

    @property
    def has_file(self):
        return bool(self.file)

    @property
    def has_link(self):
        return bool(self.external_link)
