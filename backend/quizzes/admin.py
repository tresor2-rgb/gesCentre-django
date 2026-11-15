from django.contrib import admin
from .models import Quiz, QuizQuestion, QuizOption, QuizResult


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 0


class QuizOptionInline(admin.TabularInline):
    model = QuizOption
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'get_class_groups', 'duration_minutes', 'total_points', 'is_active', 'created_at']
    list_filter = ['is_active', 'teacher__center', 'teacher']
    search_fields = ['title', 'description']
    inlines = [QuizQuestionInline]

    def get_class_groups(self, obj):
        return ", ".join([g.name for g in obj.class_groups.all()])
    get_class_groups.short_description = 'Classes'


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ['quiz', 'order', 'question_type', 'points', 'question_text']
    list_filter = ['question_type', 'quiz']
    search_fields = ['question_text']
    inlines = [QuizOptionInline]


@admin.register(QuizOption)
class QuizOptionAdmin(admin.ModelAdmin):
    list_display = ['question', 'option_text', 'is_correct']
    list_filter = ['is_correct', 'question__question_type']


@admin.register(QuizResult)
class QuizResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'quiz', 'score', 'total_points', 'completed_at']
    list_filter = ['quiz']
    search_fields = ['student__first_name', 'student__last_name']
