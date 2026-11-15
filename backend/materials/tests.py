from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from academics.models import ClassGroup
from centers.models import Center, Subject
from materials.models import SubjectMaterial
from people.models import Teacher

User = get_user_model()


class SubjectMaterialViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='manager_m',
            email='manager_m@test.com',
            password='ManagerP@ss1',
            first_name='Manager',
            last_name='Test',
            is_staff=True,
            is_superuser=True,
            role='manager',
        )
        self.center = Center.objects.create(
            name='Test Center', manager=self.manager
        )
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.teacher_user = User.objects.create_user(
            username='teacher_m',
            email='teacher_m@test.com',
            password='TeacherP@ss1',
            first_name='Teacher',
            last_name='Test',
            role='teacher',
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, center=self.center, speciality='Math'
        )
        self.group = ClassGroup.objects.create(
            name='6eme A', subject=self.subject, center=self.center
        )

    def test_list_materials_manager(self):
        SubjectMaterial.objects.create(
            title='Chapitre 1',
            subject=self.subject,
            teacher=self.teacher,
            center=self.center,
            is_published=True,
        )
        self.client.force_authenticate(user=self.manager)
        response = self.client.get('/api/materials/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_material_teacher(self):
        self.client.force_authenticate(user=self.teacher_user)
        data = {
            'title': 'Exercices',
            'description': 'Exercices de maths',
            'subject': self.subject.id,
            'teacher': self.teacher.id,
            'class_group': self.group.id,
            'center': self.center.id,
            'external_link': 'https://example.com/exercices',
        }
        response = self.client.post('/api/materials/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_student_sees_only_published(self):
        student_user = User.objects.create_user(
            username='student_m',
            email='student_m@test.com',
            password='StudentP@ss1',
            first_name='Student',
            last_name='Test',
            role='student',
        )
        SubjectMaterial.objects.create(
            title='Published', subject=self.subject, teacher=self.teacher,
            center=self.center, is_published=True,
        )
        SubjectMaterial.objects.create(
            title='Draft', subject=self.subject, teacher=self.teacher,
            center=self.center, is_published=False,
        )
        self.client.force_authenticate(user=student_user)
        response = self.client.get('/api/materials/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_material_requires_file_or_link(self):
        self.client.force_authenticate(user=self.teacher_user)
        data = {
            'title': 'Sans pièce jointe',
            'subject': self.subject.id,
            'class_group': self.group.id,
        }
        response = self.client.post('/api/materials/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
