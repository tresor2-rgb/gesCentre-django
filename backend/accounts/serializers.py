from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from centers.models import Center

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    center_id = serializers.SerializerMethodField()
    center_name = serializers.SerializerMethodField()
    student_status = serializers.SerializerMethodField()
    teacher_status = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    speciality = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'avatar', 'is_active', 'center_id',
            'center_name', 'student_status', 'teacher_status',
            'class_name', 'speciality', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_center_id(self, obj):
        try:
            if hasattr(obj, 'managed_center'):
                return obj.managed_center.id
            if hasattr(obj, 'teacher_profile'):
                return obj.teacher_profile.center_id
            if hasattr(obj, 'student_profile'):
                return obj.student_profile.center_id
        except Exception:
            pass
        return None

    def get_center_name(self, obj):
        try:
            if hasattr(obj, 'managed_center'):
                return obj.managed_center.name
            if hasattr(obj, 'teacher_profile'):
                return obj.teacher_profile.center.name
            if hasattr(obj, 'student_profile'):
                return obj.student_profile.center.name
        except Exception:
            pass
        return None

    def get_student_status(self, obj):
        try:
            return obj.student_profile.status
        except Exception:
            return None

    def get_teacher_status(self, obj):
        try:
            return 'approved' if obj.teacher_profile.is_active else 'pending'
        except Exception:
            return None

    def get_class_name(self, obj):
        try:
            profile = getattr(obj, 'student_profile', None)
            if profile:
                if profile.classe_id:
                    return profile.classe.name
                if profile.class_group_id:
                    return profile.class_group.name
        except Exception:
            pass
        return None

    def get_speciality(self, obj):
        try:
            if hasattr(obj, 'teacher_profile'):
                return obj.teacher_profile.speciality
        except Exception:
            pass
        return None


class RegisterSerializer(serializers.Serializer):
    role = serializers.CharField(required=False, default='manager')
    center_id = serializers.IntegerField(required=False)
    class_group_id = serializers.IntegerField(required=False)
    classe_id = serializers.IntegerField(required=False)
    center_name = serializers.CharField(max_length=255, required=False)
    center_address = serializers.CharField(max_length=500, required=False, default='')
    center_phone = serializers.CharField(max_length=20, required=False, default='')
    center_email = serializers.EmailField(required=False, default='')
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    def validate_email(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Un compte avec cet email existe déjà.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': 'Les mots de passe ne correspondent pas.'}
            )
        role = attrs.get('role', 'manager')
        if role == 'manager' and not attrs.get('center_name'):
            raise serializers.ValidationError({'center_name': 'Le nom du centre est requis pour un manager.'})
        if role != 'manager' and not attrs.get('center_id'):
            raise serializers.ValidationError({'center_id': 'L\'ID du centre est requis.'})
        return attrs

    def create(self, validated_data):
        role = validated_data.pop('role', 'manager')
        center_id = validated_data.pop('center_id', None)
        class_group_id = validated_data.pop('class_group_id', None)
        classe_id = validated_data.pop('classe_id', None)
        center_name = validated_data.pop('center_name', None)
        center_address = validated_data.pop('center_address', '')
        center_phone = validated_data.pop('center_phone', '')
        center_email = validated_data.pop('center_email', '')
        validated_data.pop('password_confirm')

        password = validated_data.pop('password')
        email = validated_data.get('email')

        user = User(
            username=email,
            role=role,
            **validated_data,
        )
        if role == 'manager':
            user.is_staff = True
            user.is_superuser = True

        user.set_password(password)
        user.save()

        if role == 'manager':
            Center.objects.create(
                name=center_name,
                address=center_address,
                phone=center_phone,
                email=center_email,
                manager=user,
            )
        elif role == 'teacher':
            from people.models import Teacher
            Teacher.objects.create(
                user=user,
                center_id=center_id,
                is_active=False, # Wait for approval
            )
        elif role == 'student':
            from people.models import Student, StudentRequest
            student = Student.objects.create(
                user=user,
                first_name=user.first_name,
                last_name=user.last_name,
                center_id=center_id,
                classe_id=classe_id,
                class_group_id=class_group_id,
                status='pending',
                registration_type='self_request',
            )
            StudentRequest.objects.create(
                student=student,
                center_id=center_id,
                status='pending',
                message='Nouvelle demande d’inscription à valider.',
            )

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )

    def validate_old_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Mot de passe actuel incorrect.')
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(username=value, is_active=True).exists():
            raise serializers.ValidationError(
                'Aucun compte actif trouvé avec cet email.'
            )
        return value
