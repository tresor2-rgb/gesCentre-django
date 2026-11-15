from rest_framework import serializers
from .models import SubjectMaterial


class SubjectMaterialListSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_group_name = serializers.CharField(
        source='class_group.name', read_only=True, default=None,
    )
    has_file = serializers.BooleanField(read_only=True)
    has_link = serializers.BooleanField(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = SubjectMaterial
        fields = [
            'id', 'title', 'description', 'subject', 'subject_name',
            'teacher', 'teacher_name', 'class_group', 'class_group_name',
            'center', 'has_file', 'has_link', 'file_url',
            'external_link', 'is_published', 'created_at', 'updated_at',
        ]
        read_only_fields = ['teacher', 'center']

    def get_teacher_name(self, obj):
        if obj.teacher:
            return f"{obj.teacher.first_name} {obj.teacher.last_name}"
        return None

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class SubjectMaterialDetailSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_group_name = serializers.CharField(
        source='class_group.name', read_only=True, default=None,
    )
    has_file = serializers.BooleanField(read_only=True)
    has_link = serializers.BooleanField(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = SubjectMaterial
        fields = [
            'id', 'title', 'description', 'subject', 'subject_name',
            'teacher', 'teacher_name', 'class_group', 'class_group_name',
            'center', 'file', 'file_url', 'has_file',
            'external_link', 'has_link', 'is_published',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['teacher', 'center']

    def validate(self, attrs):
        existing_file = bool(self.instance.file) if self.instance else False
        existing_link = bool(self.instance.external_link) if self.instance else False
        new_file = bool(attrs.get('file'))
        new_link = bool(attrs.get('external_link', ''))
        if not (existing_file or existing_link or new_file or new_link):
            raise serializers.ValidationError(
                {'external_link': 'Un sujet doit contenir un fichier ou un lien externe.'}
            )
        return attrs

    def get_teacher_name(self, obj):
        if obj.teacher:
            return f"{obj.teacher.first_name} {obj.teacher.last_name}"
        return None

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
