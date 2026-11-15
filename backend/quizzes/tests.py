from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from academics.models import ClassGroup
from centers.models import Center, Subject
from people.models import Teacher, Student
from quizzes.models import Quiz, QuizQuestion, QuizOption, QuizResult

User = get_user_model()


class QuizViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='manager_q',
            email='manager_q@test.com',
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
            username='teacher_q',
            email='teacher_q@test.com',
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

    def test_create_quiz(self):
        self.client.force_authenticate(user=self.teacher_user)
        data = {
            'title': 'Quiz 1',
            'description': 'First quiz',
            'teacher': self.teacher.id,
            'class_groups': [self.group.id],
            'duration_minutes': 30,
            'total_points': 10,
        }
        response = self.client.post('/api/quizzes/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_quizzes(self):
        quiz = Quiz.objects.create(
            title='Quiz 1', teacher=self.teacher, total_points=10,
        )
        quiz.class_groups.add(self.group)
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get('/api/quizzes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class QuizSubmitTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='manager_qs',
            email='manager_qs@test.com',
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
            username='teacher_qs',
            email='teacher_qs@test.com',
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
        self.quiz = Quiz.objects.create(
            title='Quiz 1', teacher=self.teacher, total_points=2,
        )
        self.quiz.class_groups.add(self.group)
        self.question = QuizQuestion.objects.create(
            quiz=self.quiz, question_text='2+2=?',
            question_type='qcm', points=1, order=0,
        )
        self.correct_option = QuizOption.objects.create(
            question=self.question, option_text='4', is_correct=True,
        )
        self.wrong_option = QuizOption.objects.create(
            question=self.question, option_text='5', is_correct=False,
        )
        self.student_user = User.objects.create_user(
            username='student_qs',
            email='student_qs@test.com',
            password='StudentP@ss1',
            first_name='Student',
            last_name='Test',
            role='student',
        )
        self.student = Student.objects.create(
            user=self.student_user, first_name='Student',
            last_name='Test', center=self.center,
            class_group=self.group, status='approved',
        )

    def test_submit_quiz_correct(self):
        self.client.force_authenticate(user=self.student_user)
        data = {
            'answers': [
                {'question_id': self.question.id,
                 'selected_option_id': self.correct_option.id},
            ]
        }
        response = self.client.post(
            f'/api/quizzes/{self.quiz.id}/submit-quiz/',
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(response.data['score']), 1.0)

    def test_submit_quiz_wrong(self):
        self.client.force_authenticate(user=self.student_user)
        data = {
            'answers': [
                {'question_id': self.question.id,
                 'selected_option_id': self.wrong_option.id},
            ]
        }
        response = self.client.post(
            f'/api/quizzes/{self.quiz.id}/submit-quiz/',
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(response.data['score']), 0.0)

    def test_submit_quiz_twice_rejected(self):
        self.client.force_authenticate(user=self.student_user)
        data = {
            'answers': [
                {'question_id': self.question.id,
                 'selected_option_id': self.correct_option.id},
            ]
        }
        self.client.post(
            f'/api/quizzes/{self.quiz.id}/submit-quiz/',
            data, format='json'
        )
        response = self.client.post(
            f'/api/quizzes/{self.quiz.id}/submit-quiz/',
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_notification_created_on_submit(self):
        from people.models import Notification

        self.client.force_authenticate(user=self.student_user)
        data = {
            'answers': [
                {'question_id': self.question.id,
                 'selected_option_id': self.correct_option.id},
            ]
        }
        response = self.client.post(
            f'/api/quizzes/{self.quiz.id}/submit-quiz/',
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        notification = Notification.objects.filter(
            recipient=self.teacher_user
        ).first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.notification_type, 'quiz_submission')
        self.assertIn('Student Test', notification.message)
        self.assertIn('6eme A', notification.message)
        self.assertIn(self.quiz.title, notification.message)
        self.assertEqual(
            notification.link, f'/teacher/quizzes/{self.quiz.id}'
        )

    def test_retake_blocked_until_teacher_reads(self):
        self.client.force_authenticate(user=self.student_user)
        data = {
            'answers': [
                {'question_id': self.question.id,
                 'selected_option_id': self.correct_option.id},
            ]
        }
        self.client.post(
            f'/api/quizzes/{self.quiz.id}/submit-quiz/',
            data, format='json'
        )

        response = self.client.post(
            f'/api/quizzes/{self.quiz.id}/submit-quiz/',
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            QuizResult.objects.filter(
                student=self.student, quiz=self.quiz
            ).count(),
            1,
        )

        self.client.force_authenticate(user=self.teacher_user)
        results_response = self.client.get(
            f'/api/quizzes/{self.quiz.id}/quiz-results/'
        )
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results_response.data), 1)
        self.assertTrue(results_response.data[0]['is_read_by_teacher'])

        self.client.force_authenticate(user=self.student_user)
        retake_response = self.client.post(
            f'/api/quizzes/{self.quiz.id}/submit-quiz/',
            data, format='json'
        )
        self.assertEqual(
            retake_response.status_code, status.HTTP_201_CREATED
        )
        self.assertEqual(
            QuizResult.objects.filter(
                student=self.student, quiz=self.quiz
            ).count(),
            2,
        )

    def test_non_student_cannot_submit(self):
        self.client.force_authenticate(user=self.teacher_user)
        data = {
            'answers': [
                {'question_id': self.question.id,
                 'selected_option_id': self.correct_option.id},
            ]
        }
        response = self.client.post(
            f'/api/quizzes/{self.quiz.id}/submit-quiz/',
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_sees_own_results_only(self):
        self.client.force_authenticate(user=self.student_user)
        data = {
            'answers': [
                {'question_id': self.question.id,
                 'selected_option_id': self.correct_option.id},
            ]
        }
        self.client.post(
            f'/api/quizzes/{self.quiz.id}/submit-quiz/', data, format='json'
        )
        response = self.client.get('/api/results/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['student'], self.student.id)
        self.assertEqual(float(response.data[0]['score']), 1.0)

        other_user = User.objects.create_user(
            username='other_s',
            email='other.s@test.com',
            password='StudentP@ss1',
            first_name='Other',
            last_name='Student',
            role='student',
        )
        Student.objects.create(
            user=other_user, first_name='Other', last_name='Student',
            center=self.center, class_group=self.group, status='approved',
        )
        self.client.force_authenticate(user=other_user)
        response = self.client.get('/api/results/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
