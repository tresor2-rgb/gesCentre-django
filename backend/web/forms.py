from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from academics.models import Classe, ClassGroup, Schedule
from centers.models import Center, ClassRoom, Subject
from materials.models import SubjectMaterial
from people.models import Student, Teacher
from quizzes.models import Quiz, QuizQuestion

User = get_user_model()


class BootstrapMixin:
    """Ajoute les classes Bootstrap et quelques attributs utiles aux widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                css = 'form-check-input'
            elif isinstance(widget, forms.Select):
                css = 'form-select'
            elif isinstance(widget, forms.SelectMultiple):
                css = 'form-select'
            elif isinstance(widget, forms.Textarea):
                css = 'form-control'
                widget.attrs.setdefault('rows', 3)
            elif isinstance(widget, forms.FileInput):
                css = 'form-control'
            else:
                css = 'form-control'

            existing = widget.attrs.get('class', '')
            if css not in existing.split():
                widget.attrs['class'] = f'{existing} {css}'.strip()

            if not field.widget.attrs.get('placeholder') and not isinstance(
                widget, (forms.Select, forms.SelectMultiple, forms.CheckboxInput,
                         forms.CheckboxSelectMultiple, forms.FileInput, forms.DateInput,
                         forms.TimeInput)
            ):
                widget.attrs['placeholder'] = field.label or name.replace('_', ' ').capitalize()


class LoginForm(BootstrapMixin, forms.Form):
    identifier = forms.CharField(
        label='Email ou nom d\'utilisateur',
        widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}),
    )
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )


class ForgotPasswordForm(BootstrapMixin, forms.Form):
    email = forms.EmailField(label='Adresse email du compte')


class ManagerRegisterForm(BootstrapMixin, forms.Form):
    center_name = forms.CharField(label='Nom du centre', max_length=200)
    center_address = forms.CharField(label='Adresse', required=False, widget=forms.Textarea)
    center_phone = forms.CharField(label='Téléphone du centre', max_length=20, required=False)
    first_name = forms.CharField(label='Prénom', max_length=150)
    last_name = forms.CharField(label='Nom', max_length=150)
    email = forms.EmailField(label='Email')
    phone = forms.CharField(label='Téléphone', max_length=20, required=False)
    password = forms.CharField(label='Mot de passe', widget=forms.PasswordInput)
    password_confirm = forms.CharField(label='Confirmer le mot de passe', widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Un compte utilise déjà cette adresse email.')
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        if password and password != cleaned.get('password_confirm'):
            self.add_error('password_confirm', 'Les mots de passe ne correspondent pas.')
        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                self.add_error('password', exc)
        return cleaned


class TeacherRegisterForm(BootstrapMixin, forms.Form):
    center = forms.ModelChoiceField(
        label='Centre', queryset=Center.objects.filter(is_active=True),
    )
    first_name = forms.CharField(label='Prénom', max_length=150)
    last_name = forms.CharField(label='Nom', max_length=150)
    email = forms.EmailField(label='Email')
    phone = forms.CharField(label='Téléphone', max_length=20, required=False)
    speciality = forms.CharField(label='Spécialité', max_length=100, required=False)
    password = forms.CharField(label='Mot de passe', widget=forms.PasswordInput)
    password_confirm = forms.CharField(label='Confirmer le mot de passe', widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Un compte utilise déjà cette adresse email.')
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        if password and password != cleaned.get('password_confirm'):
            self.add_error('password_confirm', 'Les mots de passe ne correspondent pas.')
        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                self.add_error('password', exc)
        return cleaned


class StudentRegisterForm(BootstrapMixin, forms.Form):
    center = forms.ModelChoiceField(
        label='Centre', queryset=Center.objects.filter(is_active=True),
    )
    class_group = forms.ModelChoiceField(
        label='Classe / groupe visé', required=False,
        queryset=ClassGroup.objects.select_related('classe', 'subject', 'center'),
    )
    first_name = forms.CharField(label='Prénom', max_length=150)
    last_name = forms.CharField(label='Nom', max_length=150)
    email = forms.EmailField(label='Email')
    phone = forms.CharField(label='Téléphone', max_length=20, required=False)
    parent_phone = forms.CharField(label='Téléphone du parent', max_length=20, required=False)
    date_of_birth = forms.DateField(
        label='Date de naissance', required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    password = forms.CharField(label='Mot de passe', widget=forms.PasswordInput)
    password_confirm = forms.CharField(label='Confirmer le mot de passe', widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Un compte utilise déjà cette adresse email.')
        return email

    def clean(self):
        cleaned = super().clean()
        center = cleaned.get('center')
        group = cleaned.get('class_group')
        if group and center and group.center_id != center.pk:
            self.add_error('class_group', 'Cette classe n\'appartient pas au centre sélectionné.')

        password = cleaned.get('password')
        if password and password != cleaned.get('password_confirm'):
            self.add_error('password_confirm', 'Les mots de passe ne correspondent pas.')
        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                self.add_error('password', exc)
        return cleaned


class TeacherForm(BootstrapMixin, forms.Form):
    first_name = forms.CharField(label='Prénom', max_length=150)
    last_name = forms.CharField(label='Nom', max_length=150)
    email = forms.EmailField(label='Email')
    phone = forms.CharField(label='Téléphone', max_length=20, required=False)
    speciality = forms.CharField(label='Spécialité', max_length=100, required=False)
    classrooms = forms.ModelMultipleChoiceField(
        label='Salles autorisées', required=False,
        queryset=ClassRoom.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, center=None, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.center = center
        self.teacher = teacher
        if center is not None:
            self.fields['classrooms'].queryset = ClassRoom.objects.filter(center=center, is_active=True)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        qs = User.objects.filter(username__iexact=email) | User.objects.filter(email__iexact=email)
        if self.teacher is not None:
            qs = qs.exclude(pk=self.teacher.user_id)
        if qs.exists():
            raise ValidationError('Un compte utilise déjà cette adresse email.')
        return email


class StudentForm(BootstrapMixin, forms.Form):
    first_name = forms.CharField(label='Prénom', max_length=100)
    last_name = forms.CharField(label='Nom', max_length=100)
    email = forms.EmailField(label='Email', required=False)
    phone = forms.CharField(label='Téléphone', max_length=20, required=False)
    parent_phone = forms.CharField(label='Téléphone du parent', max_length=20, required=False)
    date_of_birth = forms.DateField(
        label='Date de naissance', required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    classe = forms.ModelChoiceField(
        label='Classe', required=False, queryset=Classe.objects.none(),
    )
    class_group = forms.ModelChoiceField(
        label='Groupe de classe', required=False, queryset=ClassGroup.objects.none(),
    )
    status = forms.ChoiceField(label='Statut', choices=Student.STATUS_CHOICES, initial='approved')

    def __init__(self, *args, center=None, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.center = center
        self.student = student
        if center is not None:
            self.fields['classe'].queryset = Classe.objects.filter(center=center)
            self.fields['class_group'].queryset = ClassGroup.objects.filter(center=center).select_related(
                'classe', 'subject',
            )

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            return ''
        qs = User.objects.filter(username__iexact=email) | User.objects.filter(email__iexact=email)
        if self.student is not None and self.student.user_id:
            qs = qs.exclude(pk=self.student.user_id)
        if qs.exists():
            raise ValidationError('Un compte utilise déjà cette adresse email.')
        return email

    def clean(self):
        cleaned = super().clean()
        center = self.center
        group = cleaned.get('class_group')
        classe = cleaned.get('classe')
        if group and center and group.center_id != center.pk:
            self.add_error('class_group', 'Ce groupe n\'appartient pas à votre centre.')
        if classe and center and classe.center_id != center.pk:
            self.add_error('classe', 'Cette classe n\'appartient pas à votre centre.')
        if group and not classe:
            cleaned['classe'] = group.classe
        return cleaned


class SubjectForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'description', 'is_active']


class ClassroomForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ClassRoom
        fields = ['name', 'capacity', 'description', 'is_active']


class ClasseForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Classe
        fields = ['name']


class ClassGroupForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ClassGroup
        fields = ['name', 'classe', 'subject', 'teacher', 'classroom']
        help_texts = {'name': 'Laissez vide pour générer automatiquement « Classe - Matière ».'}

    def __init__(self, *args, center=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.center = center
        if center is not None:
            self.fields['classe'].queryset = Classe.objects.filter(center=center)
            self.fields['subject'].queryset = Subject.objects.filter(center=center, is_active=True)
            self.fields['teacher'].queryset = Teacher.objects.filter(center=center, is_active=True).select_related('user')
            self.fields['classroom'].queryset = ClassRoom.objects.filter(center=center)
            self.fields['classe'].required = True
        self.fields['name'].required = False


class ScheduleForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Schedule
        fields = [
            'title', 'class_group', 'classroom', 'day_of_week', 'start_time',
            'end_time', 'specific_date', 'is_recurring', 'color', 'status', 'description',
        ]
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'specific_date': forms.DateInput(attrs={'type': 'date'}),
            'color': forms.TextInput(attrs={'type': 'color'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, center=None, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.center = center
        self.teacher_obj = teacher
        groups = ClassGroup.objects.none()
        if teacher is not None:
            groups = ClassGroup.objects.filter(teacher=teacher)
            self.fields['class_group'].queryset = groups.select_related('classe', 'subject')
        elif center is not None:
            groups = ClassGroup.objects.filter(center=center)
            self.fields['class_group'].queryset = groups.select_related('classe', 'subject')
        if center is not None:
            self.fields['classroom'].queryset = ClassRoom.objects.filter(center=center)
        self.fields['class_group'].required = True
        self.fields['class_group'].label = 'Groupe de classe'

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        end = cleaned.get('end_time')
        if start and end and end <= start:
            self.add_error('end_time', "L'heure de fin doit être postérieure à l'heure de début.")
        group = cleaned.get('class_group')
        if group and self.center is not None and group.center_id != self.center.pk:
            self.add_error('class_group', "Ce groupe n'appartient pas à votre centre.")
        if self.teacher_obj is not None and group and group.teacher_id != self.teacher_obj.pk:
            self.add_error('class_group', "Vous ne pouvez planifier que vos propres classes.")
        return cleaned


class MaterialForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = SubjectMaterial
        fields = ['title', 'description', 'subject', 'class_group', 'file', 'external_link', 'is_published']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, center=None, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.center = center
        self.teacher_obj = teacher
        if center is not None:
            self.fields['subject'].queryset = Subject.objects.filter(center=center, is_active=True)
        if teacher is not None:
            self.fields['class_group'].queryset = ClassGroup.objects.filter(teacher=teacher)
        elif center is not None:
            self.fields['class_group'].queryset = ClassGroup.objects.filter(center=center)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('file') and not cleaned.get('external_link'):
            if not (self.instance and self.instance.pk and (self.instance.file or self.instance.external_link)):
                raise ValidationError('Ajoutez un fichier ou un lien externe.')
        return cleaned


class QuizForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'class_groups', 'duration_minutes', 'total_points', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher_obj = teacher
        if teacher is not None:
            self.fields['class_groups'].queryset = ClassGroup.objects.filter(teacher=teacher)
        self.fields['class_groups'].widget = forms.CheckboxSelectMultiple()
        self.fields['class_groups'].help_text = 'Sélectionnez les classes concernées par ce quiz.'
        self.fields['class_groups'].required = True

    def clean_class_groups(self):
        groups = self.cleaned_data['class_groups']
        if self.teacher_obj is not None:
            invalid = groups.exclude(teacher=self.teacher_obj)
            if invalid.exists():
                raise ValidationError('Vous ne pouvez cibler que vos propres classes.')
        return groups


class QuestionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = QuizQuestion
        fields = ['question_text', 'question_type', 'points', 'order', 'enable_math_keyboard', 'image']
        widgets = {'question_text': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['points'].required = False
        self.fields['order'].required = False
        if not self.is_bound and not self.instance.pk:
            self.fields['points'].initial = 1
            self.fields['order'].initial = 0

    def clean_points(self):
        return self.cleaned_data.get('points') or 1

    def clean_order(self):
        return self.cleaned_data.get('order') or 0


class ProfileForm(BootstrapMixin, forms.Form):
    first_name = forms.CharField(label='Prénom', max_length=150)
    last_name = forms.CharField(label='Nom', max_length=150)
    email = forms.EmailField(label='Email')
    phone = forms.CharField(label='Téléphone', max_length=20, required=False)
    avatar = forms.ImageField(label='Photo de profil', required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        qs = User.objects.filter(username__iexact=email) | User.objects.filter(email__iexact=email)
        if self.user is not None:
            qs = qs.exclude(pk=self.user.pk)
        if qs.exists():
            raise ValidationError('Un compte utilise déjà cette adresse email.')
        return email


class ChangePasswordForm(BootstrapMixin, forms.Form):
    current_password = forms.CharField(label='Mot de passe actuel', widget=forms.PasswordInput)
    new_password = forms.CharField(label='Nouveau mot de passe', widget=forms.PasswordInput)
    confirm_password = forms.CharField(label='Confirmer le nouveau mot de passe', widget=forms.PasswordInput)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        value = self.cleaned_data['current_password']
        if self.user is None or not self.user.check_password(value):
            raise ValidationError('Mot de passe actuel incorrect.')
        return value

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('new_password')
        if password and password != cleaned.get('confirm_password'):
            self.add_error('confirm_password', 'Les mots de passe ne correspondent pas.')
        if password:
            try:
                validate_password(password, self.user)
            except ValidationError as exc:
                self.add_error('new_password', exc)
        return cleaned
