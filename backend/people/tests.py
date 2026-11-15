from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from centers.models import Center
from people.models import Teacher, Notification

User = get_user_model()


class TeacherViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='manager_t',
            email='manager_t@test.com',
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
        self.client.force_authenticate(user=self.manager)

    def test_create_teacher(self):
        data = {
            'first_name': 'Pierre',
            'last_name': 'Dupont',
            'email': 'pierre@test.com',
            'phone': '0600000000',
            'speciality': 'Mathematics',
        }
        response = self.client.post('/api/teachers/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user_email'], 'pierre@test.com')
        teacher = Teacher.objects.get(id=response.data['id'])
        self.assertEqual(teacher.center, self.center)
        self.assertTrue(teacher.user.is_active)

    def test_list_teachers(self):
        user = User.objects.create_user(
            username='teacher1',
            email='teacher@test.com',
            password='TeacherP@ss1',
            first_name='Teacher',
            last_name='One',
            role='teacher',
        )
        Teacher.objects.create(
            user=user, center=self.center, speciality='Physics'
        )
        response = self.client.get('/api/teachers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_approve_teacher(self):
        user = User.objects.create_user(
            username='teacher2',
            email='teacher2@test.com',
            password='TeacherP@ss1',
            first_name='Teacher',
            last_name='Two',
            role='teacher',
            is_active=False,
        )
        teacher = Teacher.objects.create(
            user=user, center=self.center, speciality='Chemistry', is_active=False
        )
        response = self.client.post(f'/api/teachers/{teacher.id}/approve/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        teacher.refresh_from_db()
        self.assertTrue(teacher.is_active)

    def test_reject_teacher(self):
        user = User.objects.create_user(
            username='teacher3',
            email='teacher3@test.com',
            password='TeacherP@ss1',
            first_name='Teacher',
            last_name='Three',
            role='teacher',
        )
        teacher = Teacher.objects.create(
            user=user, center=self.center, speciality='English'
        )
        response = self.client.post(f'/api/teachers/{teacher.id}/reject/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        teacher.refresh_from_db()
        self.assertFalse(teacher.is_active)


class NotificationViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='notif_user',
            email='notif@test.com',
            password='NotifP@ss1',
            first_name='Notif',
            last_name='User',
            role='teacher',
        )
        Notification.objects.create(
            recipient=self.user,
            title='Quiz soumis',
            message='Un élève a soumis un quiz.',
            notification_type='quiz_submission',
            link='/teacher/quizzes/1',
        )
        Notification.objects.create(
            recipient=self.user,
            title='Info',
            message='Message d\u2019information.',
            notification_type='info',
        )
        self.other = User.objects.create_user(
            username='other_notif',
            email='other.notif@test.com',
            password='NotifP@ss1',
            first_name='Other',
            last_name='Notif',
            role='teacher',
        )
        Notification.objects.create(
            recipient=self.other,
            title='Autre',
            message='Ne doit pas être visible.',
        )

    def test_list_own_notifications(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        for item in response.data:
            self.assertNotEqual(item['title'], 'Autre')

    def test_unread_count(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/unread-count/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_mark_read(self):
        self.client.force_authenticate(user=self.user)
        notification = Notification.objects.filter(recipient=self.user).first()
        response = self.client.post(
            f'/api/notifications/{notification.id}/mark-read/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_read'])
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_mark_all_read(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/notifications/mark-all-read/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated'], 2)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.user, is_read=False
            ).count(),
            0,
        )

    def test_mark_read_other_user_forbidden(self):
        self.client.force_authenticate(user=self.user)
        other_notification = Notification.objects.filter(
            recipient=self.other
        ).first()
        response = self.client.post(
            f'/api/notifications/{other_notification.id}/mark-read/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
