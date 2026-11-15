from django.contrib import admin
from .models import SubjectMaterial


@admin.register(SubjectMaterial)
class SubjectMaterialAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'subject', 'teacher', 'class_group', 'center',
        'is_published', 'created_at',
    ]
    list_filter = ['is_published', 'subject', 'center']
    search_fields = ['title', 'description']
