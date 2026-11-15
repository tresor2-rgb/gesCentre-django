from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from academics.models import ClassGroup, Schedule
from centers.models import Center, Subject
from materials.models import SubjectMaterial
from people.models import Student, StudentRequest, Teacher
from quizzes.models import Quiz, QuizQuestion, QuizOption

User = get_user_model()


def make_student_user(email, center, group=None, status='approved'):
    user = User.objects.create_user(
        username=email,
        email=email,
        password='StudentP@ss1',
        first_name='Eleve',
        last_name='Test',
        role='student',
    )
    student = Student.objects.create(
        user=user, first_name='Eleve', last_name='Test',
        center=center, class_group=group, status=status,
    )
    return user, student


def make_manager(email, center_name='Manager Center'):
    user = User.objects.create_user(
        username=email,
        email=email,
        password='ManagerP@ss1',
        first_name='Admin',
        last_name='Manager',
        role='manager',
        is_staff=True,
        is_superuser=True,
    )
    center = Center.objects.create(name=center_name, manager=user)
    return user, center


class EnrollmentRequestTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager, self.center = make_manager('enr.manager@test.com')
        self.student_user, self.student = make_student_user(
            'enr.student@test.com', self.center
        )
        self.client.force_authenticate(user=self.student_user)

    def test_enrollment_request_success(self):
        response = self.client.post(
            '/api/enrollment-request/',
            {'center_id': self.center.id, 'message': 'Je veux rejoindre'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'pending')
        self.assertTrue(
            StudentRequest.objects.filter(
                student=self.student, center=self.center, status='pending'
            ).exists()
        )

    def test_enrollment_request_duplicate_pending(self):
        StudentRequest.objects.create(
            student=self.student, center=self.center, status='pending'
        )
        response = self.client.post(
            '/api/enrollment-request/',
            {'center_id': self.center.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enrollment_request_nonexistent_center(self):
        response = self.client.post(
            '/api/enrollment-request/', {'center_id': 9999}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enrollment_request_non_student_forbidden(self):
        teacher_user = User.objects.create_user(
            username='enr.teacher@test.com',
            email='enr.teacher@test.com',
            password='TeacherP@ss1',
            first_name='Prof',
            last_name='Test',
            role='teacher',
        )
        Teacher.objects.create(user=teacher_user, center=self.center)
        self.client.force_authenticate(user=teacher_user)
        response = self.client.post(
            '/api/enrollment-request/',
            {'center_id': self.center.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class StudentScheduleTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager, self.center = make_manager('sch.manager@test.com')
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.group_a = ClassGroup.objects.create(
            name='6A', subject=self.subject, center=self.center
        )
        self.group_b = ClassGroup.objects.create(
            name='6B', subject=self.subject, center=self.center
        )
        self.schedule_a = Schedule.objects.create(
            class_group=self.group_a, day_of_week=0,
            start_time='08:00', end_time='10:00', center=self.center,
        )
        self.schedule_b = Schedule.objects.create(
            class_group=self.group_b, day_of_week=1,
            start_time='08:00', end_time='10:00', center=self.center,
        )
        self.student_user, self.student = make_student_user(
            'sch.student@test.com', self.center, group=self.group_a
        )

    def test_student_sees_only_own_class_schedules(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get('/api/schedules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(self.schedule_a.id, ids)
        self.assertNotIn(self.schedule_b.id, ids)

    def test_student_without_class_sees_no_schedules(self):
        user, student = make_student_user('sch.noclass@test.com', self.center)
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/schedules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class StudentMaterialScopingTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager, self.center = make_manager('mat.manager@test.com')
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.teacher_user = User.objects.create_user(
            username='mat.teacher@test.com',
            email='mat.teacher@test.com',
            password='TeacherP@ss1',
            first_name='Prof',
            last_name='Test',
            role='teacher',
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, center=self.center, speciality='Math'
        )
        self.group_a = ClassGroup.objects.create(
            name='6A', subject=self.subject, teacher=self.teacher, center=self.center
        )
        self.group_b = ClassGroup.objects.create(
            name='6B', subject=self.subject, teacher=self.teacher, center=self.center
        )
        self.student_user, self.student = make_student_user(
            'mat.student@test.com', self.center, group=self.group_a
        )
        self.material_mine = SubjectMaterial.objects.create(
            title='Pour ma classe', subject=self.subject, teacher=self.teacher,
            center=self.center, class_group=self.group_a, is_published=True,
        )
        self.material_global = SubjectMaterial.objects.create(
            title='Global', subject=self.subject, teacher=self.teacher,
            center=self.center, class_group=None, is_published=True,
        )
        self.material_other_group = SubjectMaterial.objects.create(
            title='Autre classe', subject=self.subject, teacher=self.teacher,
            center=self.center, class_group=self.group_b, is_published=True,
        )
        self.material_draft = SubjectMaterial.objects.create(
            title='Brouillon', subject=self.subject, teacher=self.teacher,
            center=self.center, class_group=self.group_a, is_published=False,
        )
        self.client.force_authenticate(user=self.student_user)

    def test_student_sees_own_class_and_global_only(self):
        response = self.client.get('/api/materials/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item['title'] for item in response.data]
        self.assertIn('Pour ma classe', titles)
        self.assertIn('Global', titles)
        self.assertNotIn('Autre classe', titles)
        self.assertNotIn('Brouillon', titles)

    def test_student_material_detail_scoped(self):
        response = self.client.get(f'/api/materials/{self.material_mine.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(f'/api/materials/{self.material_other_group.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class StudentQuizScopingTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager, self.center = make_manager('sq.manager@test.com')
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.teacher_user = User.objects.create_user(
            username='sq.teacher@test.com',
            email='sq.teacher@test.com',
            password='TeacherP@ss1',
            first_name='Prof',
            last_name='Test',
            role='teacher',
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, center=self.center, speciality='Math'
        )
        self.group_a = ClassGroup.objects.create(
            name='6A', subject=self.subject, teacher=self.teacher, center=self.center
        )
        self.group_b = ClassGroup.objects.create(
            name='6B', subject=self.subject, teacher=self.teacher, center=self.center
        )
        self.quiz_a = Quiz.objects.create(
            title='Quiz 6A', teacher=self.teacher, total_points=5, is_active=True
        )
        self.quiz_a.class_groups.add(self.group_a)
        self.quiz_b = Quiz.objects.create(
            title='Quiz 6B', teacher=self.teacher, total_points=5, is_active=True
        )
        self.quiz_b.class_groups.add(self.group_b)
        self.quiz_inactive = Quiz.objects.create(
            title='Quiz Inactif', teacher=self.teacher, total_points=5, is_active=False
        )
        self.quiz_inactive.class_groups.add(self.group_a)
        self.student_user, self.student = make_student_user(
            'sq.student@test.com', self.center, group=self.group_a
        )
        self.client.force_authenticate(user=self.student_user)

    def test_student_sees_own_group_quizzes(self):
        response = self.client.get('/api/quizzes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(self.quiz_a.id, ids)
        self.assertNotIn(self.quiz_b.id, ids)

    def test_student_questions_only_from_own_group(self):
        question_a = QuizQuestion.objects.create(
            quiz=self.quiz_a, question_text='Q A', question_type='qcm', points=1, order=0
        )
        question_b = QuizQuestion.objects.create(
            quiz=self.quiz_b, question_text='Q B', question_type='qcm', points=1, order=0
        )
        response = self.client.get(f'/api/questions/?quiz={self.quiz_a.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(question_a.id, ids)
        self.assertNotIn(question_b.id, ids)

    def test_student_does_not_see_inactive_quiz_questions(self):
        question = QuizQuestion.objects.create(
            quiz=self.quiz_inactive, question_text='Q', question_type='qcm',
            points=1, order=0,
        )
        response = self.client.get(f'/api/questions/?quiz={self.quiz_inactive.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class StudentPublicSerializerTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager, self.center = make_manager('sp.manager@test.com')
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.teacher_user = User.objects.create_user(
            username='sp.teacher@test.com',
            email='sp.teacher@test.com',
            password='TeacherP@ss1',
            first_name='Prof',
            last_name='Test',
            role='teacher',
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, center=self.center, speciality='Math'
        )
        self.group = ClassGroup.objects.create(
            name='6A', subject=self.subject, teacher=self.teacher, center=self.center
        )
        self.quiz = Quiz.objects.create(
            title='Quiz', teacher=self.teacher, total_points=2, is_active=True
        )
        self.quiz.class_groups.add(self.group)
        self.question = QuizQuestion.objects.create(
            quiz=self.quiz, question_text='2+2=?', question_type='qcm', points=1, order=0
        )
        self.correct = QuizOption.objects.create(
            question=self.question, option_text='4', is_correct=True
        )
        self.wrong = QuizOption.objects.create(
            question=self.question, option_text='5', is_correct=False
        )
        self.student_user, self.student = make_student_user(
            'sp.student@test.com', self.center, group=self.group
        )

    def test_student_quiz_detail_hides_is_correct(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(f'/api/quizzes/{self.quiz.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        options = response.data['questions'][0]['options']
        for opt in options:
            self.assertNotIn('is_correct', opt)
            self.assertIn('option_text', opt)

    def test_student_questions_hide_is_correct(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(f'/api/questions/?quiz={self.quiz.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        options = response.data[0]['options']
        for opt in options:
            self.assertNotIn('is_correct', opt)

    def test_teacher_questions_show_is_correct(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get(f'/api/questions/?quiz={self.quiz.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('options_count', response.data[0])
        self.assertEqual(response.data[0]['options_count'], 2)
