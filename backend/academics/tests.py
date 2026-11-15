from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from academics.models import ClassGroup, Schedule
from centers.models import Center, ClassRoom, Subject
from people.models import Student, Teacher

User = get_user_model()


class ClassGroupViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='manager_a',
            email='manager_a@test.com',
            password='ManagerP@ss1',
            first_name='Manager',
            last_name='Test',
            is_staff=True,
            is_superuser=True,
            role='manager',
        )
        self.center = Center.objects.create(
            name='Test Center',
            manager=self.manager,
        )
        self.subject = Subject.objects.create(
            name='Math', center=self.center
        )
        self.classroom = ClassRoom.objects.create(
            name='Room A', center=self.center, capacity=30
        )
        self.teacher_user = User.objects.create_user(
            username='teacher_a',
            email='teacher_a@test.com',
            password='TeacherP@ss1',
            first_name='Teacher',
            last_name='Test',
            role='teacher',
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            center=self.center,
            speciality='Math',
        )
        self.client.force_authenticate(user=self.manager)

    def test_create_class_group(self):
        data = {
            'name': '6eme A',
            'subject': self.subject.id,
            'teacher': self.teacher.id,
            'classroom': self.classroom.id,
            'center': self.center.id,
        }
        response = self.client.post('/api/class-groups/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_class_groups(self):
        ClassGroup.objects.create(
            name='6eme A',
            subject=self.subject,
            center=self.center,
        )
        response = self.client.get('/api/class-groups/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_teacher_sees_students_of_own_class(self):
        group = ClassGroup.objects.create(
            name='Premiere TI',
            subject=self.subject,
            teacher=self.teacher,
            classroom=self.classroom,
            center=self.center,
        )
        Student.objects.create(
            first_name='Tresor',
            last_name='Bella',
            center=self.center,
            status='approved',
            class_group=group,
        )
        Student.objects.create(
            first_name='Inactive',
            last_name='Student',
            center=self.center,
            status='pending',
            class_group=group,
        )
        other_group = ClassGroup.objects.create(
            name='5eme B',
            subject=self.subject,
            center=self.center,
        )
        Student.objects.create(
            first_name='Autre',
            last_name='Classe',
            center=self.center,
            status='approved',
            class_group=other_group,
        )

        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get(f'/api/class-groups/{group.id}/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [s['first_name'] for s in response.data]
        self.assertEqual(names, ['Tresor'])
        for item in response.data:
            self.assertEqual(item['class_group'], group.id)
            self.assertEqual(item['status'], 'approved')

        response_other = self.client.get(
            f'/api/class-groups/{other_group.id}/students/'
        )
        self.assertEqual(response_other.status_code, status.HTTP_404_NOT_FOUND)


class ScheduleViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='manager_s',
            email='manager_s@test.com',
            password='ManagerP@ss1',
            first_name='Manager',
            last_name='Test',
            is_staff=True,
            is_superuser=True,
            role='manager',
        )
        self.center = Center.objects.create(
            name='Test Center',
            manager=self.manager,
        )
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.classroom = ClassRoom.objects.create(
            name='Room A', center=self.center, capacity=30
        )
        self.teacher_user = User.objects.create_user(
            username='teacher_s',
            email='teacher_s@test.com',
            password='TeacherP@ss1',
            first_name='Teacher',
            last_name='Test',
            role='teacher',
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            center=self.center,
            speciality='Math',
        )
        self.group = ClassGroup.objects.create(
            name='6eme A',
            subject=self.subject,
            teacher=self.teacher,
            center=self.center,
        )
        self.student = Student.objects.create(
            first_name='Alice',
            last_name='Martin',
            center=self.center,
            status='approved',
            class_group=self.group,
        )
        self.client.force_authenticate(user=self.manager)

    def test_create_schedule(self):
        data = {
            'class_group': self.group.id,
            'day_of_week': 0,
            'start_time': '08:00:00',
            'end_time': '10:00:00',
            'title': 'Maths Lundi',
        }
        response = self.client.post('/api/schedules/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_schedule_payload_includes_subject_and_students(self):
        schedule = Schedule.objects.create(
            class_group=self.group,
            day_of_week=1,
            start_time='08:00',
            end_time='10:00',
            center=self.center,
        )
        response = self.client.get('/api/schedules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()[0]
        self.assertEqual(data['subject_name'], 'Math')
        self.assertEqual(data['teacher_name'], 'Teacher Test')
        self.assertEqual(data['students'], [{'id': self.student.id, 'name': 'Alice Martin'}])

    def test_overlapping_schedule_is_rejected(self):
        Schedule.objects.create(
            class_group=self.group,
            day_of_week=0,
            start_time='08:00',
            end_time='10:00',
            center=self.center,
        )
        data = {
            'class_group': self.group.id,
            'day_of_week': 0,
            'start_time': '09:00:00',
            'end_time': '11:00:00',
            'title': 'Maths Lundi 2',
        }
        response = self.client.post('/api/schedules/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Créneau indisponible', str(response.data))

    def test_same_slot_on_another_day_is_allowed(self):
        Schedule.objects.create(
            class_group=self.group,
            day_of_week=0,
            start_time='08:00',
            end_time='10:00',
            center=self.center,
        )
        data = {
            'class_group': self.group.id,
            'day_of_week': 1,
            'start_time': '08:00:00',
            'end_time': '10:00:00',
            'title': 'Maths Mardi',
        }
        response = self.client.post('/api/schedules/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_teacher_overlap_is_rejected(self):
        other_group = ClassGroup.objects.create(
            name='5eme B',
            subject=self.subject,
            teacher=self.teacher,
            center=self.center,
        )
        Schedule.objects.create(
            class_group=self.group,
            day_of_week=2,
            start_time='08:00',
            end_time='10:00',
            center=self.center,
        )
        data = {
            'class_group': other_group.id,
            'day_of_week': 2,
            'start_time': '09:00:00',
            'end_time': '11:00:00',
            'title': 'Autre classe même prof',
        }
        response = self.client.post('/api/schedules/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_schedule_allows_same_slot(self):
        schedule = Schedule.objects.create(
            class_group=self.group,
            day_of_week=0,
            start_time='08:00',
            end_time='10:00',
            center=self.center,
        )
        data = {
            'class_group': self.group.id,
            'day_of_week': 0,
            'start_time': '08:00:00',
            'end_time': '10:00:00',
            'title': 'Maths modifié',
        }
        response = self.client.put(
            f'/api/schedules/{schedule.id}/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_end_time_before_start_is_rejected(self):
        data = {
            'class_group': self.group.id,
            'day_of_week': 0,
            'start_time': '10:00:00',
            'end_time': '08:00:00',
            'title': 'Heures inversées',
        }
        response = self.client.post('/api/schedules/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_schedules(self):
        Schedule.objects.create(
            class_group=self.group,
            day_of_week=1,
            start_time='08:00',
            end_time='10:00',
            center=self.center,
        )
        response = self.client.get('/api/schedules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
