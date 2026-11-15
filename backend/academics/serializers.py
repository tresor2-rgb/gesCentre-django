from django.db.models import Q
from rest_framework import serializers
from .models import ClassGroup, Schedule, Attendance, Classe


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    class_group_name = serializers.CharField(source='class_group.name', read_only=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 'class_group', 'class_group_name', 'student', 'student_name',
            'date', 'status', 'remarks', 'created_at', 'updated_at',
        ]

    def get_student_name(self, obj):
        return str(obj.student)


class AttendanceBulkSerializer(serializers.Serializer):
    attendance = serializers.ListField(child=serializers.DictField())

    def validate_attendance(self, value):
        for item in value:
            if 'student' not in item or 'status' not in item or 'date' not in item:
                raise serializers.ValidationError(
                    'Chaque entrée doit contenir student, status et date.'
                )
        return value


class ScheduleSerializer(serializers.ModelSerializer):
    day_display = serializers.CharField(source='get_day_of_week_display', read_only=True)
    class_group_name = serializers.CharField(source='class_group.name', read_only=True, default=None)
    subject_name = serializers.CharField(source='class_group.subject.name', read_only=True, default=None)
    teacher_name = serializers.SerializerMethodField()
    classroom_name = serializers.CharField(source='classroom.name', read_only=True, default=None)
    students = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            'id', 'class_group', 'class_group_name', 'subject_name', 'classroom', 'classroom_name',
            'day_of_week', 'day_display',
            'start_time', 'end_time',
            'title', 'description', 'color',
            'center', 'teacher', 'teacher_name',
            'students',
            'is_recurring', 'specific_date', 'status',
            'created_at', 'updated_at',
        ]

    def get_teacher_name(self, obj):
        if obj.teacher:
            return f"{obj.teacher.first_name} {obj.teacher.last_name}"
        return None

    def get_students(self, obj):
        if obj.class_group is None:
            return []
        return [
            {"id": s.id, "name": f"{s.first_name} {s.last_name}".strip() or str(s)}
            for s in obj.class_group.students.filter(status='approved')
            .order_by('last_name', 'first_name')
        ]

    def validate(self, attrs):
        instance = self.instance
        class_group = attrs.get('class_group', getattr(instance, 'class_group', None) if instance else None)
        teacher = attrs.get('teacher', getattr(instance, 'teacher', None) if instance else None)
        if teacher is None and class_group is not None:
            teacher = class_group.teacher
        day_of_week = attrs.get('day_of_week', getattr(instance, 'day_of_week', None) if instance else None)
        start_time = attrs.get('start_time', getattr(instance, 'start_time', None) if instance else None)
        end_time = attrs.get('end_time', getattr(instance, 'end_time', None) if instance else None)

        if start_time is not None and end_time is not None and start_time >= end_time:
            raise serializers.ValidationError(
                "L'heure de fin doit être postérieure à l'heure de début."
            )

        if day_of_week is not None and start_time is not None and end_time is not None:
            qs = Schedule.objects.filter(day_of_week=day_of_week)
            if instance:
                qs = qs.exclude(pk=instance.pk)
            conflict_q = Q()
            if class_group is not None:
                conflict_q |= Q(class_group=class_group)
            if teacher is not None:
                conflict_q |= Q(teacher=teacher)
            if conflict_q:
                overlaps = qs.filter(
                    conflict_q,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                )
                if overlaps.exists():
                    raise serializers.ValidationError(
                        "Créneau indisponible : cette classe ou cet enseignant est "
                        "déjà occupé(e) sur cette plage horaire."
                    )
        return attrs


class ClassGroupListSerializer(serializers.ModelSerializer):
    classe_name = serializers.CharField(source='classe.name', read_only=True, default=None)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    classroom_name = serializers.CharField(source='classroom.name', read_only=True, default=None)
    students_count = serializers.IntegerField(read_only=True)
    schedule_info = serializers.ListField(read_only=True)

    class Meta:
        model = ClassGroup
        fields = [
            'id', 'name', 'classe', 'classe_name', 'subject', 'subject_name',
            'teacher', 'teacher_name',
            'classroom', 'classroom_name', 'center', 'created_at',
            'students_count', 'schedule_info',
        ]
        validators = []

    def get_teacher_name(self, obj):
        if obj.teacher:
            return f"{obj.teacher.first_name} {obj.teacher.last_name}"
        return None

    def validate(self, attrs):
        instance = self.instance
        classe = attrs.get('classe', getattr(instance, 'classe', None) if instance else None)
        subject = attrs.get('subject', getattr(instance, 'subject', None) if instance else None)

        if classe is not None and subject is not None:
            qs = ClassGroup.objects.filter(classe=classe, subject=subject)
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'Cette matière est déjà attribuée pour cette classe. '
                    'Une matière ne peut être enseignée que par un seul enseignant par classe.'
                )
        return attrs


class ClassGroupDetailSerializer(serializers.ModelSerializer):
    classe_name = serializers.CharField(source='classe.name', read_only=True, default=None)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    classroom_name = serializers.CharField(source='classroom.name', read_only=True, default=None)
    students_count = serializers.IntegerField(read_only=True)
    schedule_info = serializers.ListField(read_only=True)
    schedules = ScheduleSerializer(many=True, read_only=True)

    class Meta:
        model = ClassGroup
        fields = [
            'id', 'name', 'classe', 'classe_name', 'subject', 'subject_name',
            'teacher', 'teacher_name',
            'classroom', 'classroom_name', 'center', 'created_at',
            'students_count', 'schedule_info', 'schedules',
        ]
        validators = []

    def get_teacher_name(self, obj):
        if obj.teacher:
            return f"{obj.teacher.first_name} {obj.teacher.last_name}"
        return None

    def validate(self, attrs):
        instance = self.instance
        classe = attrs.get('classe', getattr(instance, 'classe', None) if instance else None)
        subject = attrs.get('subject', getattr(instance, 'subject', None) if instance else None)

        if classe is not None and subject is not None:
            qs = ClassGroup.objects.filter(classe=classe, subject=subject)
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'Cette matière est déjà attribuée pour cette classe. '
                    'Une matière ne peut être enseignée que par un seul enseignant par classe.'
                )
        return attrs


class ClasseListSerializer(serializers.ModelSerializer):
    subjects_count = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = Classe
        fields = [
            'id', 'name', 'center', 'created_at',
            'subjects_count', 'students_count',
        ]
        read_only_fields = ['center']

    def get_subjects_count(self, obj):
        return getattr(obj, 'subjects_count', None) or obj.class_groups.count()

    def get_students_count(self, obj):
        return getattr(obj, 'students_count', None) or obj.students.filter(status='approved').count()


class ClasseDetailSerializer(serializers.ModelSerializer):
    subjects_count = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()
    class_groups = ClassGroupListSerializer(many=True, read_only=True)

    class Meta:
        model = Classe
        fields = [
            'id', 'name', 'center', 'created_at',
            'subjects_count', 'students_count', 'class_groups',
        ]
        read_only_fields = ['center']

    def get_subjects_count(self, obj):
        return getattr(obj, 'subjects_count', None) or obj.class_groups.count()

    def get_students_count(self, obj):
        return getattr(obj, 'students_count', None) or obj.students.filter(status='approved').count()
