from rest_framework import serializers
from .models import Quiz, QuizQuestion, QuizOption, QuizResult


class QuizOptionSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = QuizOption
        fields = ['id', 'question', 'option_text', 'is_correct', 'image', 'image_url']

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class QuizOptionPublicSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = QuizOption
        fields = ['id', 'option_text', 'image', 'image_url']

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class QuizQuestionListSerializer(serializers.ModelSerializer):
    options_count = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = QuizQuestion
        fields = [
            'id', 'quiz', 'question_text', 'image', 'image_url',
            'question_type', 'points', 'order', 'enable_math_keyboard',
            'options_count',
        ]

    def get_options_count(self, obj):
        return obj.options.count()

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class QuizQuestionDetailSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = QuizQuestion
        fields = [
            'id', 'quiz', 'question_text', 'image', 'image_url',
            'question_type', 'points', 'order', 'enable_math_keyboard',
            'options',
        ]

    def get_options(self, obj):
        user = self.context.get('request').user
        if hasattr(user, 'student_profile'):
            return QuizOptionPublicSerializer(obj.options.all(), many=True).data
        return QuizOptionSerializer(obj.options.all(), many=True).data

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class QuizQuestionPublicSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = QuizQuestion
        fields = [
            'id', 'quiz', 'question_text', 'image', 'image_url',
            'question_type', 'points', 'order', 'enable_math_keyboard',
            'options',
        ]

    def get_options(self, obj):
        return QuizOptionPublicSerializer(obj.options.all(), many=True).data

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class QuizQuestionSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    selected_option_id = serializers.IntegerField(required=False, allow_null=True)
    text_answer = serializers.CharField(required=False, allow_blank=True)


class QuizListSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    class_groups_info = serializers.SerializerMethodField()
    questions_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'teacher', 'teacher_name',
            'class_groups', 'class_groups_info', 'duration_minutes',
            'total_points', 'is_active', 'created_at', 'updated_at',
            'questions_count',
        ]
        read_only_fields = ['teacher']

    def get_teacher_name(self, obj):
        if obj.teacher:
            return f"{obj.teacher.first_name} {obj.teacher.last_name}"
        return None

    def get_class_groups_info(self, obj):
        return [{"id": g.id, "name": g.name} for g in obj.class_groups.all()]


class QuizDetailSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    class_groups_info = serializers.SerializerMethodField()
    questions_count = serializers.IntegerField(read_only=True)
    questions = QuizQuestionDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'teacher', 'teacher_name',
            'class_groups', 'class_groups_info', 'duration_minutes',
            'total_points', 'is_active', 'created_at', 'updated_at',
            'questions_count', 'questions',
        ]
        read_only_fields = ['teacher']

    def get_teacher_name(self, obj):
        if obj.teacher:
            return f"{obj.teacher.first_name} {obj.teacher.last_name}"
        return None

    def get_class_groups_info(self, obj):
        return [{"id": g.id, "name": g.name} for g in obj.class_groups.all()]


class QuizResultSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    percentage = serializers.FloatField(read_only=True)
    student_class = serializers.SerializerMethodField()

    class Meta:
        model = QuizResult
        fields = [
            'id', 'student', 'student_name', 'student_class', 'quiz', 'quiz_title',
            'score', 'total_points', 'percentage', 'is_read_by_teacher', 'completed_at',
        ]

    def get_student_name(self, obj):
        if obj.student:
            return f"{obj.student.first_name} {obj.student.last_name}"
        return None

    def get_student_class(self, obj):
        if obj.student:
            if obj.student.class_group:
                return obj.student.class_group.name
            return obj.student.class_name or ''
        return None


class QuizSubmitSerializer(serializers.Serializer):
    answers = QuizQuestionSubmitSerializer(many=True)
