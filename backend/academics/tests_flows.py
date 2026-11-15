from django.contrib.auth import get_user_model
from datetime import date

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from academics.models import Attendance, ClassGroup, Schedule
from centers.models import Center, ClassRoom, Subject
from materials.models import SubjectMaterial
from people.models import Student, Teacher
from quizzes.models import Quiz, QuizQuestion, QuizOption

User = get_user_model()


def make_teacher(email, center, speciality='Math', active=True):
    user = User.objects.create_user(
        username=email,
        email=email,
        password='TeacherP@ss1',
        first_name='Prof',
        last_name='Test',
        role='teacher',
        is_active=active,
    )
    teacher = Teacher.objects.create(
        user=user, center=center, speciality=speciality, is_active=active
    )
    return user, teacher


class AttendanceTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='att.manager@test.com',
            email='att.manager@test.com',
            password='ManagerP@ss1',
            first_name='Admin',
            last_name='Manager',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        self.center = Center.objects.create(name='Att Center', manager=self.manager)
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.teacher_user, self.teacher = make_teacher(
            'att.teacher@test.com', self.center
        )
        self.group = ClassGroup.objects.create(
            name='6eme A', subject=self.subject, teacher=self.teacher, center=self.center
        )
        self.student = Student.objects.create(
            first_name='Jean', last_name='Dupont', center=self.center,
            class_group=self.group, status='approved',
        )
        self.client.force_authenticate(user=self.teacher_user)

    def test_bulk_create_attendance(self):
        data = {
            'attendance': [
                {
                    'class_group': self.group.id,
                    'student': self.student.id,
                    'date': '2026-01-05',
                    'status': 'present',
                }
            ]
        }
        response = self.client.post(
            '/api/attendance/bulk_create/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Attendance.objects.count(), 1)
        att = Attendance.objects.get()
        self.assertEqual(att.status, 'present')

    def test_bulk_create_updates_existing(self):
        Attendance.objects.create(
            class_group=self.group, student=self.student,
            date=date(2026, 1, 5), status='absent',
        )
        data = {
            'attendance': [
                {
                    'class_group': self.group.id,
                    'student': self.student.id,
                    'date': '2026-01-05',
                    'status': 'present',
                }
            ]
        }
        self.client.post('/api/attendance/bulk_create/', data, format='json')
        self.assertEqual(Attendance.objects.count(), 1)
        att = Attendance.objects.get()
        self.assertEqual(att.status, 'present')

    def test_bulk_create_requires_fields(self):
        data = {'attendance': [{'student': self.student.id}]}
        response = self.client.post(
            '/api/attendance/bulk_create/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_attendance(self):
        Attendance.objects.create(
            class_group=self.group, student=self.student,
            date=date(2026, 1, 5), status='present',
        )
        response = self.client.get('/api/attendance/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_patch_attendance_status(self):
        att = Attendance.objects.create(
            class_group=self.group, student=self.student,
            date=date(2026, 1, 5), status='absent',
        )
        response = self.client.patch(
            f'/api/attendance/{att.id}/', {'status': 'late'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        att.refresh_from_db()
        self.assertEqual(att.status, 'late')


class TeacherScopingTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager_a = User.objects.create_user(
            username='scop.ma@test.com',
            email='scop.ma@test.com',
            password='ManagerP@ss1',
            first_name='M',
            last_name='A',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        self.manager_b = User.objects.create_user(
            username='scop.mb@test.com',
            email='scop.mb@test.com',
            password='ManagerP@ss1',
            first_name='M',
            last_name='B',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        self.center_a = Center.objects.create(name='Center A', manager=self.manager_a)
        self.center_b = Center.objects.create(name='Center B', manager=self.manager_b)
        self.subject_a = Subject.objects.create(name='Math', center=self.center_a)
        self.subject_b = Subject.objects.create(name='Math', center=self.center_b)
        self.teacher_a_user, self.teacher_a = make_teacher('scop.ta@test.com', self.center_a)
        self.teacher_b_user, self.teacher_b = make_teacher('scop.tb@test.com', self.center_b)
        self.group_a = ClassGroup.objects.create(
            name='6A', subject=self.subject_a, teacher=self.teacher_a, center=self.center_a
        )
        self.group_b = ClassGroup.objects.create(
            name='6B', subject=self.subject_b, teacher=self.teacher_b, center=self.center_b
        )
        Schedule.objects.create(
            class_group=self.group_a, day_of_week=0,
            start_time='08:00', end_time='10:00', center=self.center_a,
        )
        Schedule.objects.create(
            class_group=self.group_b, day_of_week=0,
            start_time='08:00', end_time='10:00', center=self.center_b,
        )

    def test_teacher_sees_only_own_class_groups(self):
        self.client.force_authenticate(user=self.teacher_a_user)
        response = self.client.get('/api/class-groups/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(self.group_a.id, ids)
        self.assertNotIn(self.group_b.id, ids)

    def test_teacher_sees_only_own_schedules(self):
        self.client.force_authenticate(user=self.teacher_a_user)
        response = self.client.get('/api/schedules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        schedule_a = Schedule.objects.get(class_group=self.group_a)
        schedule_b = Schedule.objects.get(class_group=self.group_b)
        self.assertIn(schedule_a.id, ids)
        self.assertNotIn(schedule_b.id, ids)

    def test_teacher_sees_only_own_center_subjects(self):
        self.client.force_authenticate(user=self.teacher_a_user)
        response = self.client.get('/api/subjects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(self.subject_a.id, ids)
        self.assertNotIn(self.subject_b.id, ids)

    def test_teacher_sees_only_own_center_classrooms(self):
        room_a = ClassRoom.objects.create(name='A', center=self.center_a, capacity=20)
        room_b = ClassRoom.objects.create(name='B', center=self.center_b, capacity=20)
        self.client.force_authenticate(user=self.teacher_a_user)
        response = self.client.get('/api/classrooms/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(room_a.id, ids)
        self.assertNotIn(room_b.id, ids)


class TeacherQuizTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='tq.manager@test.com',
            email='tq.manager@test.com',
            password='ManagerP@ss1',
            first_name='M',
            last_name='A',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        self.center = Center.objects.create(name='Quiz Center', manager=self.manager)
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.teacher_a_user, self.teacher_a = make_teacher('tq.ta@test.com', self.center)
        self.teacher_b_user, self.teacher_b = make_teacher('tq.tb@test.com', self.center)
        self.group = ClassGroup.objects.create(
            name='6eme A', subject=self.subject, teacher=self.teacher_a, center=self.center
        )
        self.quiz_a = Quiz.objects.create(
            title='Quiz A', teacher=self.teacher_a, total_points=10
        )
        self.quiz_a.class_groups.add(self.group)
        self.quiz_b = Quiz.objects.create(
            title='Quiz B', teacher=self.teacher_b, total_points=10
        )
        self.quiz_b.class_groups.add(self.group)

    def test_teacher_sees_only_own_quizzes(self):
        self.client.force_authenticate(user=self.teacher_a_user)
        response = self.client.get('/api/quizzes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertIn(self.quiz_a.id, ids)
        self.assertNotIn(self.quiz_b.id, ids)

    def test_teacher_update_quiz(self):
        self.client.force_authenticate(user=self.teacher_a_user)
        response = self.client.patch(
            f'/api/quizzes/{self.quiz_a.id}/',
            {'title': 'Quiz A Updated'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.quiz_a.refresh_from_db()
        self.assertEqual(self.quiz_a.title, 'Quiz A Updated')

    def test_teacher_delete_quiz(self):
        self.client.force_authenticate(user=self.teacher_a_user)
        response = self.client.delete(f'/api/quizzes/{self.quiz_a.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_quiz_results_teacher_only(self):
        from people.models import Student
        from quizzes.models import QuizResult
        student_user = User.objects.create_user(
            username='tq.student@test.com',
            email='tq.student@test.com',
            password='StudentP@ss1',
            first_name='S',
            last_name='T',
            role='student',
        )
        student = Student.objects.create(
            user=student_user, first_name='S', last_name='T',
            center=self.center, class_group=self.group, status='approved',
        )
        QuizResult.objects.create(
            student=student, quiz=self.quiz_a, score=5, total_points=10
        )
        self.client.force_authenticate(user=self.teacher_a_user)
        response = self.client.get(f'/api/quizzes/{self.quiz_a.id}/quiz-results/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_quiz_results_forbidden_for_non_teacher(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(f'/api/quizzes/{self.quiz_a.id}/quiz-results/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_cannot_see_other_teachers_quiz_results(self):
        from people.models import Student
        from quizzes.models import QuizResult
        student_user = User.objects.create_user(
            username='tq.student2@test.com',
            email='tq.student2@test.com',
            password='StudentP@ss1',
            first_name='S',
            last_name='T',
            role='student',
        )
        student = Student.objects.create(
            user=student_user, first_name='S', last_name='T',
            center=self.center, class_group=self.group, status='approved',
        )
        QuizResult.objects.create(
            student=student, quiz=self.quiz_b, score=5, total_points=10
        )
        self.client.force_authenticate(user=self.teacher_a_user)
        response = self.client.get(f'/api/quizzes/{self.quiz_b.id}/quiz-results/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class QuizQuestionOptionTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='qo.manager@test.com',
            email='qo.manager@test.com',
            password='ManagerP@ss1',
            first_name='M',
            last_name='A',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        self.center = Center.objects.create(name='QO Center', manager=self.manager)
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.teacher_user, self.teacher = make_teacher('qo.teacher@test.com', self.center)
        self.group = ClassGroup.objects.create(
            name='6eme A', subject=self.subject, teacher=self.teacher, center=self.center
        )
        self.quiz = Quiz.objects.create(
            title='Quiz', teacher=self.teacher, total_points=10
        )
        self.quiz.class_groups.add(self.group)
        self.client.force_authenticate(user=self.teacher_user)

    def test_create_question(self):
        data = {
            'quiz': self.quiz.id,
            'question_text': '2+2=?',
            'question_type': 'qcm',
            'points': 2,
            'order': 0,
        }
        response = self.client.post('/api/questions/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_option(self):
        question = QuizQuestion.objects.create(
            quiz=self.quiz, question_text='2+2=?', question_type='qcm',
            points=1, order=0,
        )
        data = {'question': question.id, 'option_text': '4', 'is_correct': True}
        response = self.client.post('/api/options/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update_question(self):
        question = QuizQuestion.objects.create(
            quiz=self.quiz, question_text='2+2=?', question_type='qcm',
            points=1, order=0,
        )
        response = self.client.patch(
            f'/api/questions/{question.id}/',
            {'points': 5},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        question.refresh_from_db()
        self.assertEqual(question.points, 5)

    def test_delete_question(self):
        question = QuizQuestion.objects.create(
            quiz=self.quiz, question_text='2+2=?', question_type='qcm',
            points=1, order=0,
        )
        response = self.client.delete(f'/api/questions/{question.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_option(self):
        question = QuizQuestion.objects.create(
            quiz=self.quiz, question_text='2+2=?', question_type='qcm',
            points=1, order=0,
        )
        option = QuizOption.objects.create(
            question=question, option_text='4', is_correct=True
        )
        response = self.client.delete(f'/api/options/{option.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_teacher_sees_own_questions_only(self):
        other_teacher_user, other_teacher = make_teacher('qo.other@test.com', self.center)
        other_quiz = Quiz.objects.create(
            title='Other Quiz', teacher=other_teacher, total_points=5
        )
        QuizQuestion.objects.create(
            quiz=other_quiz, question_text='Hidden', question_type='qcm',
            points=1, order=0,
        )
        response = self.client.get('/api/questions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class TeacherMaterialTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='tm2.manager@test.com',
            email='tm2.manager@test.com',
            password='ManagerP@ss1',
            first_name='M',
            last_name='A',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        self.center = Center.objects.create(name='Mat Center', manager=self.manager)
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.teacher_user, self.teacher = make_teacher('tm2.teacher@test.com', self.center)
        self.group = ClassGroup.objects.create(
            name='6eme A', subject=self.subject, teacher=self.teacher, center=self.center
        )
        self.material = SubjectMaterial.objects.create(
            title='Chapitre 1', subject=self.subject, teacher=self.teacher,
            center=self.center, class_group=self.group, is_published=True,
            external_link='https://example.com/chapitre1',
        )
        self.client.force_authenticate(user=self.teacher_user)

    def test_create_material_auto_sets_teacher_and_center(self):
        data = {
            'title': 'Exercices',
            'subject': self.subject.id,
            'class_group': self.group.id,
            'external_link': 'https://example.com/exercices',
        }
        response = self.client.post('/api/materials/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mat = SubjectMaterial.objects.get(id=response.data['id'])
        self.assertEqual(mat.teacher, self.teacher)
        self.assertEqual(mat.center, self.center)

    def test_update_material(self):
        response = self.client.patch(
            f'/api/materials/{self.material.id}/',
            {'title': 'Updated'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.material.refresh_from_db()
        self.assertEqual(self.material.title, 'Updated')

    def test_delete_material(self):
        response = self.client.delete(f'/api/materials/{self.material.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_teacher_sees_center_wide_materials(self):
        other_teacher_user, other_teacher = make_teacher('tm2.other@test.com', self.center)
        SubjectMaterial.objects.create(
            title='By other', subject=self.subject, teacher=other_teacher,
            center=self.center, is_published=True,
        )
        response = self.client.get('/api/materials/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_teacher_sees_only_own_center_materials(self):
        manager_b = User.objects.create_user(
            username='tm2.mb@test.com',
            email='tm2.mb@test.com',
            password='ManagerP@ss1',
            first_name='M',
            last_name='B',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        center_b = Center.objects.create(name='Center B', manager=manager_b)
        subject_b = Subject.objects.create(name='Physique', center=center_b)
        other_teacher_user, other_teacher = make_teacher('tm2.tb@test.com', center_b)
        SubjectMaterial.objects.create(
            title='Foreign', subject=subject_b, teacher=other_teacher,
            center=center_b, is_published=True,
        )
        response = self.client.get('/api/materials/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class ClassGroupStudentManagementTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='cgm.manager@test.com',
            email='cgm.manager@test.com',
            password='ManagerP@ss1',
            first_name='Admin',
            last_name='Manager',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        self.center = Center.objects.create(name='CGM Center', manager=self.manager)
        self.subject = Subject.objects.create(name='Math', center=self.center)
        self.group = ClassGroup.objects.create(
            name='6eme A', subject=self.subject, center=self.center,
        )
        self.student = Student.objects.create(
            first_name='Jean', last_name='Dupont', center=self.center,
            status='approved',
        )
        self.client.force_authenticate(user=self.manager)

    def test_add_student_to_class_group(self):
        response = self.client.post(
            f'/api/class-groups/{self.group.id}/students/',
            {'student_id': self.student.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertEqual(self.student.class_group, self.group)

    def test_add_student_requires_student_id(self):
        response = self.client.post(
            f'/api/class-groups/{self.group.id}/students/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_student_from_another_center_is_rejected(self):
        manager_b = User.objects.create_user(
            username='cgm.manager.b@test.com',
            email='cgm.manager.b@test.com',
            password='ManagerP@ss1',
            first_name='M',
            last_name='B',
            role='manager',
            is_staff=True,
            is_superuser=True,
        )
        center_b = Center.objects.create(name='CGM Center B', manager=manager_b)
        foreign_student = Student.objects.create(
            first_name='Foreign', last_name='Student', center=center_b,
            status='approved',
        )
        response = self.client.post(
            f'/api/class-groups/{self.group.id}/students/',
            {'student_id': foreign_student.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_remove_student_from_class_group(self):
        self.student.class_group = self.group
        self.student.save()
        response = self.client.delete(
            f'/api/class-groups/{self.group.id}/students/{self.student.id}/',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.class_group)

    def test_remove_unknown_student_returns_404(self):
        response = self.client.delete(
            f'/api/class-groups/{self.group.id}/students/999999/',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
