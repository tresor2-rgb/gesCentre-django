from rest_framework import serializers
from django.utils import timezone
from .models import Teacher, Student, StudentRequest, Notification


class UserNestedSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True)


class TeacherListSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_full_name = serializers.SerializerMethodField()
    center_name = serializers.CharField(source='center.name', read_only=True)
    classes_count = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = [
            'id', 'user', 'user_email', 'user_full_name',
            'center', 'center_name', 'speciality', 'is_active',
            'classes_count', 'created_at',
        ]
        read_only_fields = ['center']

    def get_user_full_name(self, obj):
        return obj.user.get_full_name()

    def get_classes_count(self, obj):
        return getattr(obj, 'classes_count', None) or obj.class_groups.count()


class TeacherDetailSerializer(serializers.ModelSerializer):
    user_info = UserNestedSerializer(source='user', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_full_name = serializers.SerializerMethodField()
    center_name = serializers.CharField(source='center.name', read_only=True)
    classrooms = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    classes_count = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = [
            'id', 'user', 'user_info', 'user_email', 'user_full_name',
            'center', 'center_name',
            'speciality', 'classrooms', 'is_active', 'classes_count', 'created_at',
        ]
        read_only_fields = ['center']

    def get_user_full_name(self, obj):
        return obj.user.get_full_name()

    def get_classes_count(self, obj):
        return getattr(obj, 'classes_count', None) or obj.class_groups.count()


class ClassRoomBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class StudentListSerializer(serializers.ModelSerializer):
    center_name = serializers.CharField(source='center.name', read_only=True)
    class_group_name = serializers.CharField(source='class_group.name', read_only=True, default=None)
    classe_name = serializers.CharField(source='classe.name', read_only=True, default=None)
    user_email = serializers.CharField(source='user.email', read_only=True, default=None)

    class Meta:
        model = Student
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'parent_phone',
            'date_of_birth', 'center', 'center_name', 'registration_type',
            'status', 'classe', 'classe_name', 'class_group', 'class_group_name', 'class_name',
            'user_email', 'created_at',
        ]
        read_only_fields = ['center']


class StudentDetailSerializer(serializers.ModelSerializer):
    center_name = serializers.CharField(source='center.name', read_only=True)
    class_group_name = serializers.CharField(source='class_group.name', read_only=True, default=None)
    classe_name = serializers.CharField(source='classe.name', read_only=True, default=None)
    requests = serializers.SerializerMethodField()
    user_email = serializers.CharField(source='user.email', read_only=True, default=None)

    class Meta:
        model = Student
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'parent_phone',
            'date_of_birth', 'center', 'center_name', 'registration_type',
            'status', 'classe', 'classe_name', 'class_group', 'class_group_name', 'class_name',
            'user_email', 'requests', 'created_at',
        ]
        read_only_fields = ['center']

    def get_requests(self, obj):
        return StudentRequestSerializer(obj.requests.all(), many=True).data


class StudentRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    center_name = serializers.CharField(source='center.name', read_only=True)
    class_group = serializers.PrimaryKeyRelatedField(source='student.class_group', read_only=True)
    class_group_name = serializers.CharField(source='student.class_group.name', read_only=True, default=None)

    class Meta:
        model = StudentRequest
        fields = [
            'id', 'student', 'student_name', 'center', 'center_name',
            'status', 'message', 'class_group', 'class_group_name',
            'created_at', 'processed_at',
        ]
        read_only_fields = ['center', 'status', 'processed_at']

    def get_student_name(self, obj):
        return str(obj.student)


class StudentRequestProcessSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True)


class StudentEnrollmentRequestSerializer(serializers.Serializer):
    center_id = serializers.IntegerField()
    message = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_center_id(self, value):
        from centers.models import Center
        if not Center.objects.filter(id=value).exists():
            raise serializers.ValidationError('Centre inexistant.')
        return value


class StudentResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=6, max_length=128)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'notification_type',
            'link', 'is_read', 'created_at',
        ]
        read_only_fields = fields
