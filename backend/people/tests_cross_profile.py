"""
Cross-profile interaction tests.

Chains that link multiple roles together:
  1. Manager creates student → student logs in with temp credentials
  2. Student self-enrollment → manager approves → student logs in → sees schedule
  3. Student views attendance records after teacher takes attendance
  4. Student cannot submit quiz from another group
  5. Student dashboard returns valid data
"""
from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from academics.models import Attendance, ClassGroup, Schedule
from centers.models import Center, ClassRoom, Subject
from people.models import Student, StudentRequest, Teacher
from quizzes.models import Quiz, QuizQuestion, QuizOption

User = get_user_model()


def make_manager(email, center_name='Test Center'):
    user = User.objects.create_user(
        username=email, email=email, password='ManagerP@ss1',
        first_name='Admin', last_name='Manager', role='manager',
        is_staff=True, is_superuser=True,
    )
    center = Center.objects.create(name=center_name, manager=user)
    return user, center


def make_teacher(email, center, speciality='Math'):
    user = User.objects.create_user(
        username=email, email=email, password='TeacherP@ss1',
        first_name='Prof', last_name='Test', role='teacher',
    )
    teacher = Teacher.objects.create(user=user, center=center, speciality=speciality)
    return user, teacher


class StudentLoginWithTempCredentialsTest(APITestCase):
    """Inter 2: manager creates student → student logs in."""

    def test_student_login_after_manager_creates(self):
        manager, center = make_manager('il.manager@test.com')
        subject = Subject.objects.create(name='Math', center=center)
        group = ClassGroup.objects.create(
            name='6eme A', subject=subject, center=center
        )
        client = APIClient()
        client.force_authenticate(user=manager)

        response = client.post('/api/students/', {
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'email': 'il.student@test.com',
            'center': center.id,
            'class_group': group.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        temp_password = response.data['temp_password']
        login_id = response.data['login_id']

        login_client = APIClient()
        login_response = login_client.post('/api/auth/login/', {
            'email': login_id,
            'password': temp_password,
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', login_response.data)

    def test_student_login_wrong_password_rejected(self):
        manager, center = make_manager('il2.manager@test.com')
        client = APIClient()
        client.force_authenticate(user=manager)
        client.post('/api/students/', {
            'first_name': 'Jean', 'last_name': 'Dupont',
            'email': 'il2.student@test.com', 'center': center.id,
        }, format='json')

        login_client = APIClient()
        login_response = login_client.post('/api/auth/login/', {
            'email': 'il2.student@test.com', 'password': 'WrongPassword1!',
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_401_UNAUTHORIZED)


class StudentEnrollmentApprovalLoginTest(APITestCase):
    """Inter 4: student enrolls → manager approves → student logs in."""

    def test_enrollment_then_approval_then_login(self):
        manager, center = make_manager('ea.manager@test.com')

        student_user = User.objects.create_user(
            username='ea.student@test.com', email='ea.student@test.com',
            password='StudentP@ss1', first_name='Eleve', last_name='Test',
            role='student', is_active=False,
        )
        student = Student.objects.create(
            user=student_user, first_name='Eleve', last_name='Test',
            center=center, status='pending', registration_type='self_request',
        )

        student_client = APIClient()
        student_client.force_authenticate(user=student_user)
        response = student_client.post('/api/enrollment-request/', {
            'center_id': center.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        manager_client = APIClient()
        manager_client.force_authenticate(user=manager)
        request = StudentRequest.objects.get(student=student, center=center)
        response = manager_client.post(
            f'/api/student-requests/{request.id}/approve/',
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        student_user.refresh_from_db()
        self.assertTrue(student_user.is_active)

        login_client = APIClient()
        login_response = login_client.post('/api/auth/login/', {
            'email': 'ea.student@test.com', 'password': 'StudentP@ss1',
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', login_response.data)

    def test_rejected_student_cannot_login(self):
        manager, center = make_manager('ra.manager@test.com')

        student_user = User.objects.create_user(
            username='ra.student@test.com', email='ra.student@test.com',
            password='StudentP@ss1', first_name='Eleve', last_name='Test',
            role='student', is_active=False,
        )
        student = Student.objects.create(
            user=student_user, first_name='Eleve', last_name='Test',
            center=center, status='pending', registration_type='self_request',
        )
        request = StudentRequest.objects.create(
            student=student, center=center, status='pending'
        )

        manager_client = APIClient()
        manager_client.force_authenticate(user=manager)
        manager_client.post(
            f'/api/student-requests/{request.id}/reject/', format='json'
        )

        login_client = APIClient()
        login_response = login_client.post('/api/auth/login/', {
            'email': 'ra.student@test.com', 'password': 'StudentP@ss1',
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_401_UNAUTHORIZED)


class StudentAttendanceViewTest(APITestCase):
    """Inter 6: teacher takes attendance → student sees their records."""

    def setUp(self):
        self.manager, self.center = make_manager('at.manager@test.com')
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.teacher_user, self.teacher = make_teacher(
            'at.teacher@test.com', self.center
        )
        self.group = ClassGroup.objects.create(
            name='6eme A', subject=self.subject, teacher=self.teacher,
            center=self.center,
        )
        self.student_user = User.objects.create_user(
            username='at.student@test.com', email='at.student@test.com',
            password='StudentP@ss1', first_name='Eleve', last_name='Test',
            role='student',
        )
        self.student = Student.objects.create(
            user=self.student_user, first_name='Eleve', last_name='Test',
            center=self.center, class_group=self.group, status='approved',
        )

    def test_student_sees_own_attendance(self):
        att = Attendance.objects.create(
            class_group=self.group, student=self.student,
            date=date(2026, 2, 1), status='present',
        )

        client = APIClient()
        client.force_authenticate(user=self.student_user)
        response = client.get('/api/attendance/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(att.id, ids)

    def test_student_does_not_see_other_students_attendance(self):
        other_user = User.objects.create_user(
            username='at.other@test.com', email='at.other@test.com',
            password='StudentP@ss1', first_name='Autre', last_name='Test',
            role='student',
        )
        other_student = Student.objects.create(
            user=other_user, first_name='Autre', last_name='Test',
            center=self.center, class_group=self.group, status='approved',
        )
        att_self = Attendance.objects.create(
            class_group=self.group, student=self.student,
            date=date(2026, 2, 1), status='present',
        )
        att_other = Attendance.objects.create(
            class_group=self.group, student=other_student,
            date=date(2026, 2, 1), status='absent',
        )

        client = APIClient()
        client.force_authenticate(user=self.student_user)
        response = client.get('/api/attendance/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(att_self.id, ids)
        self.assertNotIn(att_other.id, ids)

    def test_student_attendance_includes_status(self):
        att = Attendance.objects.create(
            class_group=self.group, student=self.student,
            date=date(2026, 2, 1), status='late',
        )
        client = APIClient()
        client.force_authenticate(user=self.student_user)
        response = client.get(f'/api/attendance/{att.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'late')


class StudentScheduleEndToEndTest(APITestCase):
    """Inter 13: manager creates setup → student sees schedule."""

    def test_student_sees_schedule_for_all_subjects_in_class(self):
        manager, center = make_manager('se.manager@test.com')
        subject_math = Subject.objects.create(name='Math', center=center)
        subject_physics = Subject.objects.create(name='Physique', center=center)
        teacher1_user, teacher1 = make_teacher('se.t1@test.com', center)
        teacher2_user, teacher2 = make_teacher('se.t2@test.com', center)

        from academics.models import Classe
        classe = Classe.objects.create(name='6eme A', center=center)
        group_math = ClassGroup.objects.create(
            name='6A-Math', subject=subject_math, teacher=teacher1,
            center=center, classe=classe,
        )
        group_physics = ClassGroup.objects.create(
            name='6A-Physique', subject=subject_physics, teacher=teacher2,
            center=center, classe=classe,
        )

        schedule_math = Schedule.objects.create(
            class_group=group_math, day_of_week=0,
            start_time='08:00', end_time='10:00', center=center,
        )
        schedule_physics = Schedule.objects.create(
            class_group=group_physics, day_of_week=1,
            start_time='10:00', end_time='12:00', center=center,
        )

        student_user = User.objects.create_user(
            username='se.student@test.com', email='se.student@test.com',
            password='StudentP@ss1', first_name='Eleve', last_name='Test',
            role='student',
        )
        Student.objects.create(
            user=student_user, first_name='Eleve', last_name='Test',
            center=center, classe=classe, class_group=group_math,
            status='approved',
        )

        client = APIClient()
        client.force_authenticate(user=student_user)
        response = client.get('/api/schedules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(schedule_math.id, ids)
        self.assertIn(schedule_physics.id, ids)

    def test_student_sees_quizzes_for_all_subjects(self):
        manager, center = make_manager('seq.manager@test.com')
        subject = Subject.objects.create(name='Math', center=center)
        teacher_user, teacher = make_teacher('seq.t@test.com', center)

        from academics.models import Classe
        classe = Classe.objects.create(name='6eme A', center=center)
        group = ClassGroup.objects.create(
            name='6A-Math', subject=subject, teacher=teacher,
            center=center, classe=classe,
        )

        quiz = Quiz.objects.create(
            title='Quiz Math', teacher=teacher, total_points=5, is_active=True
        )
        quiz.class_groups.add(group)

        student_user = User.objects.create_user(
            username='seq.student@test.com', email='seq.student@test.com',
            password='StudentP@ss1', first_name='Eleve', last_name='Test',
            role='student',
        )
        Student.objects.create(
            user=student_user, first_name='Eleve', last_name='Test',
            center=center, classe=classe, class_group=group,
            status='approved',
        )

        client = APIClient()
        client.force_authenticate(user=student_user)
        response = client.get('/api/quizzes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(quiz.id, ids)


class StudentQuizCrossGroupBlockTest(APITestCase):
    """Inter 8: student in group A cannot submit quiz for group B."""

    def test_student_cannot_submit_other_groups_quiz(self):
        manager, center = make_manager('xg.manager@test.com')
        subject = Subject.objects.create(name='Math', center=center)
        teacher_user, teacher = make_teacher('xg.teacher@test.com', center)

        group_a = ClassGroup.objects.create(
            name='6A', subject=subject, teacher=teacher, center=center
        )
        group_b = ClassGroup.objects.create(
            name='6B', subject=subject, teacher=teacher, center=center
        )

        quiz_b = Quiz.objects.create(
            title='Quiz 6B', teacher=teacher, total_points=5, is_active=True
        )
        quiz_b.class_groups.add(group_b)

        question = QuizQuestion.objects.create(
            quiz=quiz_b, question_text='2+2=?', question_type='qcm',
            points=1, order=0,
        )
        option = QuizOption.objects.create(
            question=question, option_text='4', is_correct=True,
        )

        student_user = User.objects.create_user(
            username='xg.student@test.com', email='xg.student@test.com',
            password='StudentP@ss1', first_name='Eleve', last_name='Test',
            role='student',
        )
        Student.objects.create(
            user=student_user, first_name='Eleve', last_name='Test',
            center=center, class_group=group_a, status='approved',
        )

        client = APIClient()
        client.force_authenticate(user=student_user)
        response = client.post(
            f'/api/quizzes/{quiz_b.id}/submit-quiz/',
            {'answers': [{'question_id': question.id, 'selected_option_id': option.id}]},
            format='json',
        )
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ])

    def test_student_cannot_see_other_groups_quiz_detail(self):
        manager, center = make_manager('xgd.manager@test.com')
        subject = Subject.objects.create(name='Math', center=center)
        teacher_user, teacher = make_teacher('xgd.teacher@test.com', center)

        group_a = ClassGroup.objects.create(
            name='6A', subject=subject, teacher=teacher, center=center
        )
        group_b = ClassGroup.objects.create(
            name='6B', subject=subject, teacher=teacher, center=center
        )

        quiz_b = Quiz.objects.create(
            title='Quiz 6B', teacher=teacher, total_points=5, is_active=True
        )
        quiz_b.class_groups.add(group_b)

        student_user = User.objects.create_user(
            username='xgd.student@test.com', email='xgd.student@test.com',
            password='StudentP@ss1', first_name='Eleve', last_name='Test',
            role='student',
        )
        Student.objects.create(
            user=student_user, first_name='Eleve', last_name='Test',
            center=center, class_group=group_a, status='approved',
        )

        client = APIClient()
        client.force_authenticate(user=student_user)
        response = client.get(f'/api/quizzes/{quiz_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class StudentDashboardTest(APITestCase):
    """Student dashboard returns valid data."""

    def test_student_dashboard_returns_data(self):
        manager, center = make_manager('sd.manager@test.com')
        subject = Subject.objects.create(name='Math', center=center)
        teacher_user, teacher = make_teacher('sd.teacher@test.com', center)

        group = ClassGroup.objects.create(
            name='6A', subject=subject, teacher=teacher, center=center
        )
        Schedule.objects.create(
            class_group=group, day_of_week=0,
            start_time='08:00', end_time='10:00', center=center,
        )

        student_user = User.objects.create_user(
            username='sd.student@test.com', email='sd.student@test.com',
            password='StudentP@ss1', first_name='Eleve', last_name='Test',
            role='student',
        )
        Student.objects.create(
            user=student_user, first_name='Eleve', last_name='Test',
            center=center, class_group=group, status='approved',
        )

        client = APIClient()
        client.force_authenticate(user=student_user)
        response = client.get('/api/auth/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('quizzes_count', response.data)
        self.assertIn('sessions_today', response.data)
        self.assertIn('attendance_rate', response.data)

    def test_student_without_classe_returns_empty_dashboard(self):
        manager, center = make_manager('sdwc.manager@test.com')
        student_user = User.objects.create_user(
            username='sdwc.student@test.com', email='sdwc.student@test.com',
            password='StudentP@ss1', first_name='Eleve', last_name='Test',
            role='student',
        )
        Student.objects.create(
            user=student_user, first_name='Eleve', last_name='Test',
            center=center, status='approved',
        )
        client = APIClient()
        client.force_authenticate(user=student_user)
        response = client.get('/api/auth/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_groups'], 0)
        self.assertEqual(response.data['attendance_rate'], 0.0)
