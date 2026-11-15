from django.db import models


class Quiz(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey('people.Teacher', on_delete=models.CASCADE, related_name='quizzes')
    class_groups = models.ManyToManyField('academics.ClassGroup', related_name='quizzes')
    duration_minutes = models.PositiveIntegerField(default=60)
    total_points = models.PositiveIntegerField(default=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def questions_count(self):
        return self.questions.count()


class QuizQuestion(models.Model):
    QUESTION_TYPE_CHOICES = (
        ('qcm', 'QCM'),
        ('true_false', 'Vrai/Faux'),
        ('short_answer', 'Réponse courte'),
    )

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    image = models.ImageField(upload_to='quiz_questions/', null=True, blank=True)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    points = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    enable_math_keyboard = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}: {self.question_text[:50]}"


class QuizOption(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=500, blank=True)
    image = models.ImageField(upload_to='quiz_options/', null=True, blank=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.option_text or '(image)'} ({'\u2713' if self.is_correct else '\u2717'})"


class QuizResult(models.Model):
    student = models.ForeignKey('people.Student', on_delete=models.CASCADE, related_name='quiz_results')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='results')
    score = models.FloatField(default=0)
    total_points = models.PositiveIntegerField(default=0)
    is_read_by_teacher = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f"{self.student} - {self.quiz.title}: {self.score}/{self.total_points}"

    @property
    def percentage(self):
        if self.total_points == 0:
            return 0
        return round((self.score / self.total_points) * 100, 1)
