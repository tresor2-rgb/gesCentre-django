from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from centers.models import Center, ClassRoom, Subject

User = get_user_model()


class CenterViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='ManagerP@ss1',
            first_name='Manager',
            last_name='Test',
            is_staff=True,
            is_superuser=True,
            role='manager',
        )
        self.center = Center.objects.create(
            name='Test Center',
            address='123 Test St',
            phone='+22501020304',
            email='center@test.com',
            manager=self.manager,
        )

    def test_list_centers_public(self):
        response = self.client.get('/api/centers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_center(self):
        response = self.client.get(f'/api/centers/{self.center.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Center')

    def test_create_center_authenticated(self):
        new_manager = User.objects.create_user(
            username='manager2',
            email='manager2@test.com',
            password='ManagerP@ss1',
            first_name='Manager2',
            last_name='Test',
            is_staff=True,
            is_superuser=True,
            role='manager',
        )
        self.client.force_authenticate(user=new_manager)
        data = {
            'name': 'New Center',
            'address': '456 New St',
            'phone': '+22505060708',
            'email': 'new@test.com',
        }
        response = self.client.post('/api/centers/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update_center_manager(self):
        self.client.force_authenticate(user=self.manager)
        data = {'name': 'Updated Center'}
        response = self.client.patch(
            f'/api/centers/{self.center.id}/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SubjectViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='manager_sub',
            email='manager_sub@test.com',
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

    def test_create_subject(self):
        data = {'name': 'Mathematics', 'description': 'Math subject'}
        response = self.client.post('/api/subjects/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_subjects(self):
        Subject.objects.create(name='Physics', center=self.center)
        response = self.client.get('/api/subjects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ClassRoomViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='manager_cr',
            email='manager_cr@test.com',
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

    def test_create_classroom(self):
        data = {'name': 'Room A1', 'capacity': 30}
        response = self.client.post('/api/classrooms/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_classrooms(self):
        ClassRoom.objects.create(name='Room B1', center=self.center, capacity=25)
        response = self.client.get('/api/classrooms/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
