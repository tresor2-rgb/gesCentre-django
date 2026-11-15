from django.contrib import admin
from .models import ClassGroup, Schedule


class ScheduleInline(admin.TabularInline):
    model = Schedule
    extra = 0


@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'teacher', 'classroom', 'center', 'created_at']
    list_filter = ['center', 'subject', 'teacher']
    search_fields = ['name']
    inlines = [ScheduleInline]


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['class_group', 'day_of_week', 'start_time', 'end_time', 'classroom']
    list_filter = ['day_of_week', 'class_group__center']
