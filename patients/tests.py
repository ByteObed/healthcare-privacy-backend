from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from organisations.models import Organisation
from .models import Patient


class PatientPermissionTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='hospA_perm_test', password='testpass123')
        self.org_a = Organisation.objects.create(
            user=self.user_a, name='Hospital A Perm Test', organisation_type='hospital', location='Korle Bu'
        )

        self.user_b = User.objects.create_user(username='hospB_perm_test', password='testpass123')
        self.org_b = Organisation.objects.create(
            user=self.user_b, name='Hospital B Perm Test', organisation_type='hospital', location='Komfo Anokye'
        )

        # User with NO linked organisation (e.g. a plain admin account)
        self.orphan_user = User.objects.create_user(username='orphan_test', password='testpass123')

        self.patient_a = Patient.objects.create(
            organisation=self.org_a,
            patient_id='PERM001',
            name='Permission Test Patient',
            age=30,
            gender='F',
            diagnosis='Diabetes',
            medication='Metformin',
        )

        self.token_a = self.client.post('/api/token/', {'username': 'hospA_perm_test', 'password': 'testpass123'}).data['access']
        self.token_b = self.client.post('/api/token/', {'username': 'hospB_perm_test', 'password': 'testpass123'}).data['access']
        self.token_orphan = self.client.post('/api/token/', {'username': 'orphan_test', 'password': 'testpass123'}).data['access']

    def auth_header(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get('/api/patients/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_hospital_a_can_see_own_patients(self):
        response = self.client.get('/api/patients/', **self.auth_header(self.token_a))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_hospital_b_cannot_see_hospital_a_patients(self):
        response = self.client.get('/api/patients/', **self.auth_header(self.token_b))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_hospital_b_cannot_access_hospital_a_patient_detail_directly(self):
        response = self.client.get(f'/api/patients/{self.patient_a.id}/', **self.auth_header(self.token_b))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_without_organisation_gets_clean_403(self):
        response = self.client.get('/api/patients/', **self.auth_header(self.token_orphan))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)