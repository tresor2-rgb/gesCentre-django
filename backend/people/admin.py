from django.contrib import admin
from .models import Teacher, Student, StudentRequest


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['user', 'center', 'speciality', 'is_active', 'created_at']
    list_filter = ['center', 'is_active']
    search_fields = ['user__first_name', 'user__last_name', 'user__email']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'first_name', 'last_name', 'phone', 'center',
        'registration_type', 'status', 'created_at',
    ]
    list_filter = ['center', 'status', 'registration_type']
    search_fields = ['first_name', 'last_name', 'phone']


@admin.register(StudentRequest)
class StudentRequestAdmin(admin.ModelAdmin):
    list_display = ['student', 'center', 'status', 'created_at', 'processed_at']
    list_filter = ['status', 'center']
    search_fields = ['student__first_name', 'student__last_name']
