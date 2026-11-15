from rest_framework import serializers
from .models import Center, ClassRoom, Subject


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'description', 'center', 'is_active']
        read_only_fields = ['center']


class ClassRoomSerializer(serializers.ModelSerializer):
    center_name = serializers.CharField(source='center.name', read_only=True)
    groups_using_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ClassRoom
        fields = [
            'id', 'name', 'capacity', 'description', 'center',
            'center_name', 'is_active', 'groups_using_count', 'created_at',
        ]
        read_only_fields = ['center']


class CenterListSerializer(serializers.ModelSerializer):
    classrooms_count = serializers.SerializerMethodField()
    teachers_count = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = Center
        fields = [
            'id', 'name', 'address', 'phone', 'email', 'logo',
            'manager', 'is_active', 'classrooms_count', 'teachers_count',
            'students_count', 'created_at', 'updated_at',
        ]

    def get_classrooms_count(self, obj):
        return obj.classrooms.count()

    def get_teachers_count(self, obj):
        return obj.teachers.count()

    def get_students_count(self, obj):
        return obj.students.count()


class CenterDetailSerializer(serializers.ModelSerializer):
    classrooms = ClassRoomSerializer(many=True, read_only=True)
    teachers_count = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = Center
        fields = [
            'id', 'name', 'address', 'phone', 'email', 'logo',
            'manager', 'is_active', 'classrooms', 'teachers_count',
            'students_count', 'created_at', 'updated_at',
        ]

    def get_teachers_count(self, obj):
        return obj.teachers.count()

    def get_students_count(self, obj):
        return obj.students.count()
