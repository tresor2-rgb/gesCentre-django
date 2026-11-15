from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class RegisterViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = '/api/auth/register/'

    def test_register_manager(self):
        data = {
            'role': 'manager',
            'center_name': 'Test Center',
            'center_address': '123 Test St',
            'center_phone': '+22501020304',
            'center_email': 'center@test.com',
            'first_name': 'Admin',
            'last_name': 'Manager',
            'email': 'admin@test.com',
            'password': 'SecureP@ss1',
            'password_confirm': 'SecureP@ss1',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        user = User.objects.get(email='admin@test.com')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_register_student(self):
        manager_data = {
            'role': 'manager',
            'center_name': 'Test Center',
            'center_email': 'center@test.com',
            'first_name': 'Admin',
            'last_name': 'Manager',
            'email': 'adminreg@test.com',
            'password': 'SecureP@ss1',
            'password_confirm': 'SecureP@ss1',
        }
        self.client.post(self.register_url, manager_data, format='json')
        center = User.objects.get(email='adminreg@test.com').managed_center

        data = {
            'role': 'student',
            'center_id': center.id,
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'email': 'jean@test.com',
            'password': 'StudentP@ss1',
            'password_confirm': 'StudentP@ss1',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='jean@test.com')
        self.assertEqual(user.role, 'student')

    def test_register_password_mismatch(self):
        data = {
            'role': 'manager',
            'center_name': 'Test Center',
            'first_name': 'Admin',
            'last_name': 'Manager',
            'email': 'admin2@test.com',
            'password': 'SecureP@ss1',
            'password_confirm': 'DifferentPass1',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email(self):
        data = {
            'role': 'manager',
            'center_name': 'Test Center',
            'first_name': 'Admin',
            'last_name': 'Manager',
            'email': 'admin3@test.com',
            'password': 'SecureP@ss1',
            'password_confirm': 'SecureP@ss1',
        }
        self.client.post(self.register_url, data, format='json')
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.login_url = '/api/auth/login/'
        self.user = User.objects.create_user(
            username='test@test.com',
            email='test@test.com',
            password='TestP@ss1',
            first_name='Test',
            last_name='User',
        )

    def test_login_with_email(self):
        data = {'email': 'test@test.com', 'password': 'TestP@ss1'}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)

    def test_login_with_username(self):
        data = {'email': 'test@test.com', 'password': 'TestP@ss1'}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_wrong_password(self):
        data = {'email': 'test@test.com', 'password': 'WrongPass'}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        data = {'email': 'noone@test.com', 'password': 'TestP@ss1'}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MeViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.me_url = '/api/auth/me/'
        self.user = User.objects.create_user(
            username='meuser@test.com',
            email='meuser@test.com',
            password='TestP@ss1',
            first_name='Test',
            last_name='User',
            role='student',
        )

    def test_me_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'meuser@test.com')

    def test_me_unauthenticated(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ChangePasswordViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/auth/change-password/'
        self.user = User.objects.create_user(
            username='chguser@test.com',
            email='chguser@test.com',
            password='OldP@ss1',
            first_name='Test',
            last_name='User',
        )
        self.client.force_authenticate(user=self.user)

    def test_change_password_success(self):
        data = {'old_password': 'OldP@ss1', 'new_password': 'NewP@ss123'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewP@ss123'))

    def test_change_password_wrong_old(self):
        data = {'old_password': 'WrongPass', 'new_password': 'NewP@ss123'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ForgotPasswordViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/auth/forgot-password/'
        self.user = User.objects.create_user(
            username='fp@test.com',
            email='fp@test.com',
            password='OldP@ss1',
            first_name='Test',
            last_name='User',
        )

    def test_forgot_password_success(self):
        data = {'email': 'fp@test.com'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('temp_password', response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(response.data['temp_password']))

    def test_forgot_password_nonexistent(self):
        data = {'email': 'noone@test.com'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/auth/logout/'
        self.user = User.objects.create_user(
            username='logout@test.com',
            email='logout@test.com',
            password='TestP@ss1',
            first_name='Test',
            last_name='User',
        )
        self.client.force_authenticate(user=self.user)

    def test_logout(self):
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(
            self.url,
            {'refresh': str(refresh)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_missing_refresh(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_invalid_refresh(self):
        response = self.client.post(
            self.url, {'refresh': 'invalid-token'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TeacherRegisterTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = '/api/auth/register/'
        manager_data = {
            'role': 'manager',
            'center_name': 'Test Center',
            'center_email': 'centert@test.com',
            'first_name': 'Admin',
            'last_name': 'Manager',
            'email': 'admint@test.com',
            'password': 'SecureP@ss1',
            'password_confirm': 'SecureP@ss1',
        }
        self.client.post(self.register_url, manager_data, format='json')
        self.center = User.objects.get(email='admint@test.com').managed_center

    def test_register_teacher(self):
        data = {
            'role': 'teacher',
            'center_id': self.center.id,
            'first_name': 'Marie',
            'last_name': 'Curie',
            'email': 'marie@test.com',
            'password': 'TeacherP@ss1',
            'password_confirm': 'TeacherP@ss1',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='marie@test.com')
        self.assertEqual(user.role, 'teacher')
        self.assertTrue(hasattr(user, 'teacher_profile'))
        self.assertFalse(user.teacher_profile.is_active)

    def test_register_teacher_reports_pending_status(self):
        data = {
            'role': 'teacher',
            'center_id': self.center.id,
            'first_name': 'Marie',
            'last_name': 'Curie',
            'email': 'marie3@test.com',
            'password': 'TeacherP@ss1',
            'password_confirm': 'TeacherP@ss1',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['teacher_status'], 'pending')

        token = response.data['access_token']
        me = self.client.get(
            '/api/auth/me/', HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data['teacher_status'], 'pending')

    def test_teacher_status_approved_after_manager_approval(self):
        data = {
            'role': 'teacher',
            'center_id': self.center.id,
            'first_name': 'Marie',
            'last_name': 'Curie',
            'email': 'marie4@test.com',
            'password': 'TeacherP@ss1',
            'password_confirm': 'TeacherP@ss1',
        }
        response = self.client.post(self.register_url, data, format='json')
        token = response.data['access_token']
        teacher = User.objects.get(email='marie4@test.com').teacher_profile

        manager_user = User.objects.get(email='admint@test.com')
        self.client.force_authenticate(user=manager_user)
        approve = self.client.post(f'/api/teachers/{teacher.id}/approve/')
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(user=None)

        me = self.client.get(
            '/api/auth/me/', HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data['teacher_status'], 'approved')

    def test_register_teacher_without_center_id(self):
        data = {
            'role': 'teacher',
            'first_name': 'Marie',
            'last_name': 'Curie',
            'email': 'marie2@test.com',
            'password': 'TeacherP@ss1',
            'password_confirm': 'TeacherP@ss1',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_manager_without_center_name(self):
        data = {
            'role': 'manager',
            'first_name': 'M',
            'last_name': 'Manager',
            'email': 'mman@test.com',
            'password': 'SecureP@ss1',
            'password_confirm': 'SecureP@ss1',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TokenRefreshTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/auth/refresh/'
        self.user = User.objects.create_user(
            username='refresh@test.com',
            email='refresh@test.com',
            password='TestP@ss1',
            first_name='Test',
            last_name='User',
        )

    def test_refresh_with_refresh_key(self):
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(
            self.url, {'refresh': str(refresh)}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_refresh_with_refresh_token_key(self):
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(
            self.url, {'refresh_token': str(refresh)}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_refresh_invalid(self):
        response = self.client.post(
            self.url, {'refresh': 'invalid'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserProfileViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/auth/profile/'
        self.user = User.objects.create_user(
            username='profile@test.com',
            email='profile@test.com',
            password='TestP@ss1',
            first_name='Test',
            last_name='User',
            role='student',
            phone='0600000000',
        )
        self.client.force_authenticate(user=self.user)

    def test_get_profile(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'profile@test.com')

    def test_update_profile(self):
        data = {'first_name': 'New', 'last_name': 'Name', 'phone': '0700000000'}
        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'New')
        self.assertEqual(self.user.phone, '0700000000')

    def test_update_profile_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/auth/dashboard/'
        self.manager = User.objects.create_user(
            username='dashmanager@test.com',
            email='dashmanager@test.com',
            password='ManagerP@ss1',
            first_name='Admin',
            last_name='Manager',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        from centers.models import Center
        from academics.models import ClassGroup, Classe
        from centers.models import Subject
        self.center = Center.objects.create(
            name='Dash Center', manager=self.manager
        )
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.classe = Classe.objects.create(name='6eme A', center=self.center)
        self.group = ClassGroup.objects.create(
            name='6eme A', classe=self.classe, subject=self.subject, center=self.center
        )

    def test_dashboard_manager(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in [
            'total_students', 'total_teachers', 'total_classrooms',
            'total_classes', 'total_quizzes', 'pending_requests',
            'sessions_today', 'attendance_rate', 'recent_students',
            'recent_requests',
        ]:
            self.assertIn(key, response.data)
        self.assertEqual(response.data['total_classes'], 1)
        self.assertEqual(response.data['total_subjects_assigned'], 1)

    def test_dashboard_teacher(self):
        from people.models import Teacher
        teacher_user = User.objects.create_user(
            username='dashteacher@test.com',
            email='dashteacher@test.com',
            password='TeacherP@ss1',
            first_name='Prof',
            last_name='Test',
            role='teacher',
        )
        Teacher.objects.create(
            user=teacher_user, center=self.center, speciality='Math'
        )
        self.client.force_authenticate(user=teacher_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_students', response.data)

    def test_dashboard_student_no_center(self):
        student_user = User.objects.create_user(
            username='dashstudent@test.com',
            email='dashstudent@test.com',
            password='StudentP@ss1',
            first_name='Eleve',
            last_name='Test',
            role='student',
        )
        self.client.force_authenticate(user=student_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MeViewDetailTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.me_url = '/api/auth/me/'
        from centers.models import Center
        self.manager = User.objects.create_user(
            username='medmanager@test.com',
            email='medmanager@test.com',
            password='ManagerP@ss1',
            first_name='Admin',
            last_name='Manager',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        self.center = Center.objects.create(
            name='Me Center', manager=self.manager
        )

    def test_me_teacher_fields(self):
        from people.models import Teacher
        teacher_user = User.objects.create_user(
            username='meteacher@test.com',
            email='meteacher@test.com',
            password='TeacherP@ss1',
            first_name='Prof',
            last_name='Test',
            role='teacher',
        )
        Teacher.objects.create(
            user=teacher_user, center=self.center, speciality='Math'
        )
        self.client.force_authenticate(user=teacher_user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['center_id'], self.center.id)
        self.assertEqual(response.data['center_name'], 'Me Center')
        self.assertEqual(response.data['speciality'], 'Math')

    def test_me_student_fields(self):
        from academics.models import ClassGroup
        from centers.models import Subject
        from people.models import Student
        subject = Subject.objects.create(name='Math', center=self.center)
        group = ClassGroup.objects.create(
            name='6eme A', subject=subject, center=self.center
        )
        student_user = User.objects.create_user(
            username='mestudent@test.com',
            email='mestudent@test.com',
            password='StudentP@ss1',
            first_name='Eleve',
            last_name='Test',
            role='student',
        )
        Student.objects.create(
            user=student_user,
            first_name='Eleve',
            last_name='Test',
            center=self.center,
            class_group=group,
            status='approved',
        )
        self.client.force_authenticate(user=student_user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['center_id'], self.center.id)
        self.assertEqual(response.data['student_status'], 'approved')
        self.assertEqual(response.data['class_name'], '6eme A')
