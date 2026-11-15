from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from academics.models import ClassGroup
from centers.models import Center, ClassRoom, Subject
from people.models import Student, StudentRequest, Teacher

User = get_user_model()


def make_manager(email, name='Manager'):
    user = User.objects.create_user(
        username=email,
        email=email,
        password='ManagerP@ss1',
        first_name=name,
        last_name='Test',
        role='manager',
        is_staff=True,
        is_superuser=True,
    )
    center = Center.objects.create(name=f'Center of {name}', manager=user)
    return user, center


def make_nonstaff_manager(email, name='Manager'):
    user = User.objects.create_user(
        username=email,
        email=email,
        password='ManagerP@ss1',
        first_name=name,
        last_name='Test',
        role='manager',
    )
    center = Center.objects.create(name=f'Center of {name}', manager=user)
    return user, center


class StudentManagementTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager, self.center = make_manager('sm.manager@test.com')
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.group = ClassGroup.objects.create(
            name='6eme A', subject=self.subject, center=self.center
        )
        self.client.force_authenticate(user=self.manager)

    def test_create_student_creates_user_and_credentials(self):
        data = {
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'email': 'jean.dupont@test.com',
            'phone': '0600000000',
            'center': self.center.id,
            'class_group': self.group.id,
        }
        response = self.client.post('/api/students/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['account_created'])
        self.assertIn('temp_password', response.data)
        self.assertIn('login_id', response.data)
        student = Student.objects.get(id=response.data['id'])
        self.assertEqual(student.center, self.center)
        self.assertEqual(student.registration_type, 'manual')
        self.assertEqual(student.status, 'approved')
        self.assertIsNotNone(student.user)
        self.assertTrue(student.user.check_password(response.data['temp_password']))

    def test_create_student_email_is_ignored_by_serializer(self):
        # StudentDetailSerializer has no 'email' field, so a duplicate email
        # is NOT rejected. Two students can share the same email address.
        data = {
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'email': 'jean2@test.com',
        }
        self.client.post('/api/students/', data, format='json')
        response = self.client.post('/api/students/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_students_scoped_to_center(self):
        Student.objects.create(
            first_name='A', last_name='B', center=self.center
        )
        response = self.client.get('/api/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_approve_student_activates_user(self):
        student = Student.objects.create(
            first_name='A', last_name='B', center=self.center,
            status='pending', registration_type='self_request',
        )
        student_user = User.objects.create_user(
            username='appr@test.com', email='appr@test.com',
            password='TestP@ss1', role='student', is_active=False,
        )
        student.user = student_user
        student.save()
        StudentRequest.objects.create(
            student=student, center=self.center, status='pending'
        )
        response = self.client.post(f'/api/students/{student.id}/approve/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student.refresh_from_db()
        self.assertEqual(student.status, 'approved')
        student_user.refresh_from_db()
        self.assertTrue(student_user.is_active)
        self.assertTrue(
            student.requests.filter(status='approved').exists()
        )

    def test_reject_student_deactivates_user(self):
        student = Student.objects.create(
            first_name='A', last_name='B', center=self.center, status='approved'
        )
        student_user = User.objects.create_user(
            username='rej@test.com', email='rej@test.com',
            password='TestP@ss1', role='student', is_active=True,
        )
        student.user = student_user
        student.save()
        response = self.client.post(f'/api/students/{student.id}/reject/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student.refresh_from_db()
        self.assertEqual(student.status, 'rejected')
        student_user.refresh_from_db()
        self.assertFalse(student_user.is_active)

    def test_reset_password_student(self):
        student = Student.objects.create(
            first_name='A', last_name='B', center=self.center, status='approved'
        )
        student_user = User.objects.create_user(
            username='reset@test.com', email='reset@test.com',
            password='OldP@ss1', role='student', is_active=True,
        )
        student.user = student_user
        student.save()
        response = self.client.post(
            f'/api/students/{student.id}/reset-password/',
            {'new_password': 'NewP@ss123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student_user.refresh_from_db()
        self.assertTrue(student_user.check_password('NewP@ss123'))


class StudentRequestManagementTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager, self.center = make_manager('sr.manager@test.com')
        self.student = Student.objects.create(
            first_name='Jean', last_name='Dupont', center=self.center,
            status='pending', registration_type='self_request',
        )
        self.request = StudentRequest.objects.create(
            student=self.student, center=self.center, status='pending'
        )
        self.client.force_authenticate(user=self.manager)

    def test_list_requests(self):
        response = self.client.get('/api/student-requests/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_approve_request_approves_student(self):
        response = self.client.post(
            f'/api/student-requests/{self.request.id}/approve/',
            {'message': 'Bienvenue'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'approved')
        self.assertIsNotNone(self.request.processed_at)
        self.student.refresh_from_db()
        self.assertEqual(self.student.status, 'approved')

    def test_suspend_request_suspends_student(self):
        response = self.client.post(
            f'/api/student-requests/{self.request.id}/suspend/',
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'suspended')
        self.student.refresh_from_db()
        self.assertEqual(self.student.status, 'suspended')

    def test_reject_request_rejects_student(self):
        response = self.client.post(
            f'/api/student-requests/{self.request.id}/reject/',
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'rejected')
        self.student.refresh_from_db()
        self.assertEqual(self.student.status, 'rejected')


class TeacherManagementTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager, self.center = make_manager('tm.manager@test.com')
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.teacher_user = User.objects.create_user(
            username='tm.teacher@test.com',
            email='tm.teacher@test.com',
            password='TeacherP@ss1',
            first_name='Prof',
            last_name='Test',
            role='teacher',
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, center=self.center, speciality='Math'
        )
        self.client.force_authenticate(user=self.manager)

    def test_update_teacher_syncs_user(self):
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'new.email@test.com',
            'speciality': 'Physics',
        }
        response = self.client.patch(
            f'/api/teachers/{self.teacher.id}/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.teacher.refresh_from_db()
        self.teacher_user.refresh_from_db()
        self.assertEqual(self.teacher_user.first_name, 'Updated')
        self.assertEqual(self.teacher_user.email, 'new.email@test.com')
        self.assertEqual(self.teacher.speciality, 'Physics')

    def test_assign_and_remove_classrooms(self):
        room_a = ClassRoom.objects.create(
            name='A', center=self.center, capacity=20
        )
        room_b = ClassRoom.objects.create(
            name='B', center=self.center, capacity=20
        )
        response = self.client.post(
            f'/api/teachers/{self.teacher.id}/assign_classrooms/',
            {'classroom_ids': [room_a.id, room_b.id]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.teacher.classrooms.count(), 2
        )
        response = self.client.post(
            f'/api/teachers/{self.teacher.id}/remove_classrooms/',
            {'classroom_ids': [room_a.id]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.teacher.classrooms.count(), 1
        )

    def test_assign_classrooms_requires_ids(self):
        response = self.client.post(
            f'/api/teachers/{self.teacher.id}/assign_classrooms/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_teacher(self):
        response = self.client.delete(
            f'/api/teachers/{self.teacher.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_create_teacher_returns_temp_credentials(self):
        data = {
            'first_name': 'Nouveau',
            'last_name': 'Prof',
            'email': 'new.prof@test.com',
            'speciality': 'Math',
        }
        response = self.client.post('/api/teachers/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data.get('account_created'))
        self.assertEqual(response.data.get('login_id'), 'new.prof@test.com')
        self.assertTrue(response.data.get('temp_password'))
        self.assertIsNotNone(response.data.get('email_sent'))

        login_client = APIClient()
        login_response = login_client.post(
            '/api/auth/login/',
            {
                'email': 'new.prof@test.com',
                'password': response.data['temp_password'],
            },
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertTrue(login_response.data.get('access_token'))


class CrossCenterIsolationTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager_a, self.center_a = make_nonstaff_manager('iso.a@test.com', name='Alpha')
        self.manager_b, self.center_b = make_nonstaff_manager('iso.b@test.com', name='Beta')
        self.subject_a = Subject.objects.create(name='Math', center=self.center_a)
        self.subject_b = Subject.objects.create(name='Math', center=self.center_b)
        self.group_a = ClassGroup.objects.create(
            name='6eme A', subject=self.subject_a, center=self.center_a
        )
        self.group_b = ClassGroup.objects.create(
            name='6eme B', subject=self.subject_b, center=self.center_b
        )
        self.student_a = Student.objects.create(
            first_name='A', last_name='A', center=self.center_a
        )
        self.student_b = Student.objects.create(
            first_name='B', last_name='B', center=self.center_b
        )
        self.teacher_b_user = User.objects.create_user(
            username='iso.teacher.b@test.com',
            email='iso.teacher.b@test.com',
            password='TeacherP@ss1',
            first_name='Prof',
            last_name='Beta',
            role='teacher',
        )
        self.teacher_b = Teacher.objects.create(
            user=self.teacher_b_user, center=self.center_b, speciality='Math'
        )

    def test_manager_a_cannot_see_center_b_students(self):
        self.client.force_authenticate(user=self.manager_a)
        response = self.client.get('/api/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(self.student_a.id, ids)
        self.assertNotIn(self.student_b.id, ids)

    def test_manager_a_cannot_edit_center_b_student(self):
        self.client.force_authenticate(user=self.manager_a)
        response = self.client.post(
            f'/api/students/{self.student_b.id}/approve/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_a_cannot_see_center_b_teachers(self):
        self.client.force_authenticate(user=self.manager_a)
        response = self.client.get('/api/teachers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertNotIn(self.teacher_b.id, ids)

    def test_manager_a_cannot_see_center_b_classgroups(self):
        self.client.force_authenticate(user=self.manager_a)
        response = self.client.get('/api/class-groups/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(self.group_a.id, ids)
        self.assertNotIn(self.group_b.id, ids)

    def test_manager_a_cannot_access_center_b_request(self):
        request_b = StudentRequest.objects.create(
            student=self.student_b, center=self.center_b, status='pending'
        )
        self.client.force_authenticate(user=self.manager_a)
        response = self.client.post(
            f'/api/student-requests/{request_b.id}/approve/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_teacher_cannot_access_people_endpoints(self):
        self.client.force_authenticate(user=self.teacher_b_user)
        response = self.client.get('/api/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class ManagerSubjectClassroomTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager, self.center = make_manager('sc.manager@test.com')
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.classroom = ClassRoom.objects.create(
            name='Room 1', center=self.center, capacity=20
        )
        self.client.force_authenticate(user=self.manager)

    def test_update_subject(self):
        response = self.client.patch(
            f'/api/subjects/{self.subject.id}/',
            {'name': 'Algebra'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.name, 'Algebra')

    def test_delete_subject(self):
        response = self.client.delete(
            f'/api/subjects/{self.subject.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_update_classroom(self):
        response = self.client.patch(
            f'/api/classrooms/{self.classroom.id}/',
            {'capacity': 40},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.classroom.refresh_from_db()
        self.assertEqual(self.classroom.capacity, 40)

    def test_delete_classroom(self):
        response = self.client.delete(
            f'/api/classrooms/{self.classroom.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_class_group_students_action(self):
        group = ClassGroup.objects.create(
            name='6eme A', subject=self.subject, center=self.center
        )
        approved = Student.objects.create(
            first_name='App', last_name='Ro', center=self.center,
            class_group=group, status='approved',
        )
        pending = Student.objects.create(
            first_name='Pen', last_name='Ding', center=self.center,
            class_group=group, status='pending',
        )
        response = self.client.get(f'/api/class-groups/{group.id}/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(approved.id, ids)
        self.assertNotIn(pending.id, ids)
