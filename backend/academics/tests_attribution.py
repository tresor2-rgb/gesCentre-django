from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from academics.models import ClassGroup, Classe, Schedule
from centers.models import Center, ClassRoom, Subject
from materials.models import SubjectMaterial
from people.models import Student, Teacher

User = get_user_model()


class ClasseViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='classe_manager',
            email='classe_manager@test.com',
            password='ManagerP@ss1',
            first_name='Manager',
            last_name='Test',
            is_staff=True,
            is_superuser=True,
            role='manager',
        )
        self.center = Center.objects.create(
            name='Test Center', manager=self.manager,
        )
        self.client.force_authenticate(user=self.manager)

    def test_create_classe(self):
        response = self.client.post(
            '/api/classes/', {'name': '6eme A'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], '6eme A')
        self.assertEqual(response.data['center'], self.center.id)

    def test_list_classes_scoped_to_center(self):
        Classe.objects.create(name='6eme A', center=self.center)
        other = Center.objects.create(name='Autre Centre')
        Classe.objects.create(name='6eme B', center=other)

        response = self.client.get('/api/classes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([c['name'] for c in response.data], ['6eme A'])

    def test_detail_includes_attributions(self):
        classe = Classe.objects.create(name='6eme A', center=self.center)
        subject = Subject.objects.create(name='Math', center=self.center)
        ClassGroup.objects.create(
            name='6eme A - Math', classe=classe, subject=subject, center=self.center,
        )

        response = self.client.get(f'/api/classes/{classe.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subjects_count'], 1)
        self.assertEqual(len(response.data['class_groups']), 1)
        self.assertEqual(response.data['class_groups'][0]['subject_name'], 'Math')


class SubjectAssignmentTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='assign_manager',
            email='assign_manager@test.com',
            password='ManagerP@ss1',
            first_name='Manager',
            last_name='Test',
            is_staff=True,
            is_superuser=True,
            role='manager',
        )
        self.center = Center.objects.create(
            name='Test Center', manager=self.manager,
        )
        self.classe = Classe.objects.create(name='6eme A', center=self.center)
        self.math = Subject.objects.create(name='Math', center=self.center)
        self.physique = Subject.objects.create(name='Physique', center=self.center)
        self.room_a = ClassRoom.objects.create(name='Room A', center=self.center, capacity=30)
        self.room_b = ClassRoom.objects.create(name='Room B', center=self.center, capacity=30)

        self.teacher_a = Teacher.objects.create(
            user=User.objects.create_user(
                username='t_a', email='t_a@test.com', password='P@ss12345678',
                first_name='Jean', last_name='Dupont', role='teacher',
            ),
            center=self.center,
        )
        self.teacher_b = Teacher.objects.create(
            user=User.objects.create_user(
                username='t_b', email='t_b@test.com', password='P@ss12345678',
                first_name='Marie', last_name='Curie', role='teacher',
            ),
            center=self.center,
        )
        self.client.force_authenticate(user=self.manager)

    def _payload(self, subject, teacher, room, name=None):
        return {
            'name': name or f'6eme A - {subject.name}',
            'classe': self.classe.id,
            'subject': subject.id,
            'teacher': teacher.id,
            'classroom': room.id,
            'center': self.center.id,
        }

    def test_assign_subject_to_classe(self):
        response = self.client.post(
            '/api/class-groups/', self._payload(self.math, self.teacher_a, self.room_a),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['classe'], self.classe.id)
        self.assertEqual(response.data['subject_name'], 'Math')
        self.assertEqual(response.data['teacher_name'], 'Jean Dupont')
        self.assertEqual(response.data['classroom_name'], 'Room A')

    def test_a_class_can_have_multiple_subjects(self):
        self.client.post(
            '/api/class-groups/', self._payload(self.math, self.teacher_a, self.room_a),
            format='json',
        )
        response = self.client.post(
            '/api/class-groups/', self._payload(self.physique, self.teacher_b, self.room_b),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.classe.class_groups.count(), 2)

    def test_same_subject_same_classe_is_rejected(self):
        self.client.post(
            '/api/class-groups/', self._payload(self.math, self.teacher_a, self.room_a),
            format='json',
        )
        response = self.client.post(
            '/api/class-groups/', self._payload(self.math, self.teacher_b, self.room_b),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('déjà attribuée', str(response.data))
        self.assertEqual(self.classe.class_groups.count(), 1)

    def test_update_own_assignment_is_allowed(self):
        group = ClassGroup.objects.create(
            name='6eme A - Math', classe=self.classe, subject=self.math,
            teacher=self.teacher_a, classroom=self.room_a, center=self.center,
        )
        response = self.client.put(
            f'/api/class-groups/{group.id}/',
            self._payload(self.math, self.teacher_b, self.room_b),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group.refresh_from_db()
        self.assertEqual(group.teacher_id, self.teacher_b.id)


class StudentAllSubjectsTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='student_view_manager',
            email='sv_manager@test.com',
            password='ManagerP@ss1',
            first_name='Manager',
            last_name='Test',
            is_staff=True,
            is_superuser=True,
            role='manager',
        )
        self.center = Center.objects.create(
            name='Test Center', manager=self.manager,
        )
        self.classe = Classe.objects.create(name='6eme A', center=self.center)
        self.other_classe = Classe.objects.create(name='6eme B', center=self.center)
        self.math = Subject.objects.create(name='Math', center=self.center)
        self.physique = Subject.objects.create(name='Physique', center=self.center)
        self.room = ClassRoom.objects.create(name='Room A', center=self.center, capacity=30)

        self.teacher = Teacher.objects.create(
            user=User.objects.create_user(
                username='sv_teacher', email='sv_teacher@test.com', password='P@ss12345678',
                first_name='Jean', last_name='Dupont', role='teacher',
            ),
            center=self.center,
        )

        self.math_group = ClassGroup.objects.create(
            name='6eme A - Math', classe=self.classe, subject=self.math,
            teacher=self.teacher, classroom=self.room, center=self.center,
        )
        self.phys_group = ClassGroup.objects.create(
            name='6eme A - Physique', classe=self.classe, subject=self.physique,
            teacher=self.teacher, classroom=self.room, center=self.center,
        )
        self.other_group = ClassGroup.objects.create(
            name='6eme B - Math', classe=self.other_classe, subject=self.math,
            teacher=self.teacher, classroom=self.room, center=self.center,
        )

        self.student_user = User.objects.create_user(
            username='sv_student', email='sv_student@test.com', password='P@ss12345678',
            first_name='Alice', last_name='Martin', role='student',
        )
        self.student = Student.objects.create(
            user=self.student_user, first_name='Alice', last_name='Martin',
            center=self.center, status='approved', classe=self.classe,
        )
        self.client.force_authenticate(user=self.student_user)

    def test_student_sees_materials_for_all_his_subjects(self):
        SubjectMaterial.objects.create(
            title='Cours de math', subject=self.math, teacher=self.teacher,
            class_group=self.math_group, center=self.center, is_published=True,
        )
        SubjectMaterial.objects.create(
            title='Cours de physique', subject=self.physique, teacher=self.teacher,
            class_group=self.phys_group, center=self.center, is_published=True,
        )
        SubjectMaterial.objects.create(
            title='Cours autre classe', subject=self.math, teacher=self.teacher,
            class_group=self.other_group, center=self.center, is_published=True,
        )

        response = self.client.get('/api/materials/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [m['title'] for m in response.data]
        self.assertIn('Cours de math', titles)
        self.assertIn('Cours de physique', titles)
        self.assertNotIn('Cours autre classe', titles)

    def test_student_sees_schedules_for_all_his_subjects(self):
        Schedule.objects.create(
            class_group=self.math_group, classroom=self.room, day_of_week=0,
            start_time='08:00', end_time='10:00', center=self.center,
        )
        Schedule.objects.create(
            class_group=self.phys_group, classroom=self.room, day_of_week=0,
            start_time='10:00', end_time='12:00', center=self.center,
        )

        response = self.client.get('/api/schedules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        subjects = {s['subject_name'] for s in response.data}
        self.assertEqual(subjects, {'Math', 'Physique'})
