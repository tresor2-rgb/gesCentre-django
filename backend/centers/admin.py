from django.contrib import admin
from .models import Center, ClassRoom, Subject


@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'manager', 'created_at']
    search_fields = ['name', 'email']
    list_filter = ['created_at']


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'center', 'capacity', 'is_active']
    search_fields = ['name']
    list_filter = ['center', 'is_active']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
