from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from organisations.models import Organisation
from patients.models import Patient
from .models import SharedEncryptedRecord, AnonymizedDataset


class PrivacyTechniqueTests(APITestCase):
    def setUp(self):
        # Create Hospital A
        self.user_a = User.objects.create_user(username='hospitalA_test', password='testpass123')
        self.org_a = Organisation.objects.create(
            user=self.user_a, name='Hospital A Test', organisation_type='hospital', location='Korle Bu'
        )

        # Create Hospital B
        self.user_b = User.objects.create_user(username='hospitalB_test', password='testpass123')
        self.org_b = Organisation.objects.create(
            user=self.user_b, name='Hospital B Test', organisation_type='hospital', location='Komfo Anokye'
        )

        # Create a test patient under Hospital A
        self.patient = Patient.objects.create(
            organisation=self.org_a,
            patient_id='TEST001',
            name='Test Patient',
            age=40,
            gender='M',
            phone_number='0244000000',
            diagnosis='Hypertension',
            medication='Lisinopril',
        )

        # Get JWT tokens
        response_a = self.client.post('/api/token/', {'username': 'hospitalA_test', 'password': 'testpass123'})
        self.token_a = response_a.data['access']

        response_b = self.client.post('/api/token/', {'username': 'hospitalB_test', 'password': 'testpass123'})
        self.token_b = response_b.data['access']

    def auth_header(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    # --- ENCRYPTION ---

    def test_send_encrypted_record(self):
        response = self.client.post(
            '/api/privacy/encryption/send/',
            {'patient_id': 'TEST001', 'receiver_id': self.org_b.id},
            **self.auth_header(self.token_a)
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SharedEncryptedRecord.objects.count(), 1)

    def test_full_encryption_flow_send_key_decrypt(self):
        send_response = self.client.post(
            '/api/privacy/encryption/send/',
            {'patient_id': 'TEST001', 'receiver_id': self.org_b.id},
            **self.auth_header(self.token_a)
        )
        record_id = send_response.data['id']

        key_response = self.client.get(
            f'/api/privacy/encryption/{record_id}/key/',
            **self.auth_header(self.token_b)
        )
        self.assertEqual(key_response.status_code, status.HTTP_200_OK)
        key = key_response.data['encryption_key']

        # Second key request should fail (one-time use)
        second_key_response = self.client.get(
            f'/api/privacy/encryption/{record_id}/key/',
            **self.auth_header(self.token_b)
        )
        self.assertEqual(second_key_response.status_code, status.HTTP_403_FORBIDDEN)

        decrypt_response = self.client.post(
            f'/api/privacy/encryption/{record_id}/decrypt/',
            {'encryption_key': key},
            **self.auth_header(self.token_b)
        )
        self.assertEqual(decrypt_response.status_code, status.HTTP_200_OK)
        self.assertTrue(Patient.objects.filter(organisation=self.org_b, patient_id='TEST001').exists())

    def test_decrypt_with_wrong_key_fails(self):
        send_response = self.client.post(
            '/api/privacy/encryption/send/',
            {'patient_id': 'TEST001', 'receiver_id': self.org_b.id},
            **self.auth_header(self.token_a)
        )
        record_id = send_response.data['id']

        decrypt_response = self.client.post(
            f'/api/privacy/encryption/{record_id}/decrypt/',
            {'encryption_key': 'wrong_key_obviously_invalid'},
            **self.auth_header(self.token_b)
        )
        self.assertEqual(decrypt_response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- ANONYMIZATION ---

    def test_export_anonymized_dataset(self):
        response = self.client.post(
            '/api/privacy/anonymization/export/',
            {'receiver_id': self.org_b.id, 'diagnosis_filter': 'Hypertension'},
            **self.auth_header(self.token_a)
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AnonymizedDataset.objects.count(), 1)
        # Confirm name and patient_id are NOT in the anonymized output
        self.assertNotIn('Test Patient', str(response.data))
        self.assertNotIn('TEST001', str(response.data))

    # --- MASKING ---

    def test_masked_patient_view(self):
        response = self.client.get('/api/privacy/masking/view/', **self.auth_header(self.token_a))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        masked = response.data[0]
        # Full name should never appear unmasked
        self.assertNotEqual(masked['name'], 'Test Patient')
        self.assertIn('*', masked['name'])
        self.assertIn('*', masked['masked_phone'])

    # --- DIFFERENTIAL PRIVACY ---

    def test_differential_privacy_query_returns_noisy_count(self):
        response = self.client.post(
            '/api/privacy/differential-privacy/query/',
            {
                'target_organisation_id': self.org_a.id,
                'query_type': 'count_by_diagnosis',
                'diagnosis': 'Hypertension',
            },
            **self.auth_header(self.token_b)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('noisy_result', response.data)
        self.assertIn('epsilon', response.data)
        # True count is 1, noisy result should be a non-negative integer
        self.assertGreaterEqual(response.data['noisy_result'], 0)

    def test_differential_privacy_average_age(self):
        response = self.client.post(
            '/api/privacy/differential-privacy/query/',
            {'target_organisation_id': self.org_a.id, 'query_type': 'average_age'},
            **self.auth_header(self.token_b)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('noisy_result', response.data)