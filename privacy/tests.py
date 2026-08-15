from unittest.mock import patch, Mock
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from organisations.models import Organisation
from organisations.utils import generate_rsa_keypair
from patients.models import Patient
from .models import SharedEncryptedRecord, AnonymizedDataset
from .utils import (
    generate_session_key,
    encrypt_data_with_session_key,
    encrypt_session_key_with_public_key,
    sign_data,
)


class HybridEncryptionTests(APITestCase):
    def setUp(self):
        # Simulate Hospital A (the "local" server under test)
        self.user_a = User.objects.create_user(username='hospA_crypto_test', password='testpass123')
        priv_a, pub_a = generate_rsa_keypair()
        self.org_a = Organisation.objects.create(
            user=self.user_a, name='Hospital A Test', organisation_type='hospital',
            location='Korle Bu', public_key=pub_a, private_key=priv_a,
        )

        self.patient = Patient.objects.create(
            organisation=self.org_a, patient_id='CRYPTO001', name='Test Patient',
            age=40, gender='M', phone_number='0244000000',
            diagnosis='Hypertension', medication='Lisinopril',
        )

        self.token_a = self.client.post(
            '/api/token/', {'username': 'hospA_crypto_test', 'password': 'testpass123'}
        ).data['access']

        # A separate keypair simulating a REMOTE receiver hospital (never actually run as a server)
        self.remote_priv, self.remote_pub = generate_rsa_keypair()

    def auth_header(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    @patch('privacy.views.requests.post')
    @patch('privacy.views.requests.get')
    def test_send_encrypted_record_reaches_out_correctly(self, mock_get, mock_post):
        """Sending should fetch the receiver's public key and POST the encrypted payload."""
        mock_get.return_value = Mock(status_code=200, json=lambda: {
            'organisation_name': 'Remote Hospital', 'public_key': self.remote_pub
        })
        mock_get.return_value.raise_for_status = lambda: None
        mock_post.return_value = Mock(status_code=201)
        mock_post.return_value.raise_for_status = lambda: None

        response = self.client.post(
            '/api/privacy/encryption/send/',
            {'patient_id': 'CRYPTO001', 'receiver_url': 'http://127.0.0.1:9999'},
            **self.auth_header(self.token_a)
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_get.assert_called_once()
        mock_post.assert_called_once()

    def test_receive_encrypted_record_stores_it_locally(self):
        """The receive endpoint should accept an incoming payload with no auth required."""
        payload = {
            "sender_name": "Remote Hospital",
            "sender_url": "http://127.0.0.1:9999",
            "patient_id_reference": "REMOTE001",
            "encrypted_payload": "fake_ciphertext",
            "encrypted_session_key": "fake_encrypted_key",
            "signature": "fake_signature",
        }
        response = self.client.post('/api/privacy/encryption/receive/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SharedEncryptedRecord.objects.count(), 1)

    @patch('privacy.views.requests.get')
    def test_decrypt_full_roundtrip_with_verified_signature(self, mock_get):
        """Simulates a full send->receive->decrypt cycle using real crypto, mocking only the network hop."""
        patient_data = {
            "patient_id": "CRYPTO001", "name": "Test Patient", "age": 40,
            "gender": "M", "phone_number": "0244000000",
            "diagnosis": "Hypertension", "medication": "Lisinopril",
        }

        # Simulate a REMOTE sender encrypting for OUR org_a's public key
        session_key = generate_session_key()
        encrypted_payload = encrypt_data_with_session_key(patient_data, session_key)
        encrypted_session_key = encrypt_session_key_with_public_key(session_key, self.org_a.public_key)
        signature = sign_data(patient_data, self.remote_priv)

        record = SharedEncryptedRecord.objects.create(
            sender_name="Remote Hospital", sender_url="http://127.0.0.1:9999",
            patient_id_reference="CRYPTO001",
            encrypted_payload=encrypted_payload,
            encrypted_session_key=encrypted_session_key,
            signature=signature,
        )

        # Mock fetching the REMOTE sender's public key during signature verification
        mock_get.return_value = Mock(status_code=200, json=lambda: {'public_key': self.remote_pub})

        response = self.client.post(
            f'/api/privacy/encryption/{record.id}/decrypt/',
            **self.auth_header(self.token_a)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_decrypted'])
        self.assertTrue(response.data['signature_verified'])
        self.assertEqual(response.data['decrypted_payload']['name'], 'Test Patient')

        # Confirm a real Patient record was created from the decrypted data
        self.assertTrue(Patient.objects.filter(organisation=self.org_a, patient_id='CRYPTO001', name='Test Patient').exists())

    @patch('privacy.views.requests.get')
    def test_decrypt_with_tampered_signature_fails_verification(self, mock_get):
        """If the signature doesn't match, signature_verified should be False (data still decrypts, but isn't trusted)."""
        patient_data = {"patient_id": "CRYPTO002", "name": "Tampered", "age": 1, "gender": "M", "phone_number": "0", "diagnosis": "x", "medication": "x"}

        session_key = generate_session_key()
        encrypted_payload = encrypt_data_with_session_key(patient_data, session_key)
        encrypted_session_key = encrypt_session_key_with_public_key(session_key, self.org_a.public_key)

        # Sign with a DIFFERENT, unrelated key than the one whose public key we'll present
        wrong_priv, _ = generate_rsa_keypair()
        signature = sign_data(patient_data, wrong_priv)

        record = SharedEncryptedRecord.objects.create(
            sender_name="Remote Hospital", sender_url="http://127.0.0.1:9999",
            patient_id_reference="CRYPTO002",
            encrypted_payload=encrypted_payload,
            encrypted_session_key=encrypted_session_key,
            signature=signature,
        )

        mock_get.return_value = Mock(status_code=200, json=lambda: {'public_key': self.remote_pub})

        response = self.client.post(
            f'/api/privacy/encryption/{record.id}/decrypt/',
            **self.auth_header(self.token_a)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['signature_verified'])


class AnonymizationDistributedTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='hospA_anon_test', password='testpass123')
        priv_a, pub_a = generate_rsa_keypair()
        self.org_a = Organisation.objects.create(
            user=self.user_a, name='Hospital A Anon Test', organisation_type='hospital',
            location='Korle Bu', public_key=pub_a, private_key=priv_a,
        )
        Patient.objects.create(
            organisation=self.org_a, patient_id='ANON001', name='Real Name',
            age=35, gender='F', phone_number='0244000001',
            diagnosis='Hypertension', medication='Amlodipine',
        )
        self.token_a = self.client.post(
            '/api/token/', {'username': 'hospA_anon_test', 'password': 'testpass123'}
        ).data['access']

    def auth_header(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    @patch('privacy.views.requests.post')
    @patch('privacy.views.requests.get')
    def test_export_anonymized_dataset_strips_identity(self, mock_get, mock_post):
        mock_get.return_value = Mock(status_code=200, json=lambda: {'organisation_name': 'Remote Hospital'})
        mock_get.return_value.raise_for_status = lambda: None
        mock_post.return_value = Mock(status_code=201)
        mock_post.return_value.raise_for_status = lambda: None

        response = self.client.post(
            '/api/privacy/anonymization/export/',
            {'receiver_url': 'http://127.0.0.1:9999', 'diagnosis_filter': 'Hypertension'},
            **self.auth_header(self.token_a)
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Confirm what was actually POSTed contains no real name/patient_id
        sent_payload = mock_post.call_args.kwargs['json']
        sent_str = str(sent_payload)
        self.assertNotIn('Real Name', sent_str)
        self.assertNotIn('ANON001', sent_str)

    def test_receive_anonymized_dataset_stores_locally(self):
        payload = {
            "sender_name": "Remote Hospital", "sender_url": "http://127.0.0.1:9999",
            "filter_criteria": "diagnosis=Hypertension",
            "records": [
                {"anonymized_label": "Patient_001", "age_range": "30-40", "gender": "F", "diagnosis": "Hypertension", "medication": "Amlodipine"}
            ],
        }
        response = self.client.post('/api/privacy/anonymization/receive/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AnonymizedDataset.objects.count(), 1)


class DifferentialPrivacyDistributedTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='hospA_dp_test', password='testpass123')
        priv_a, pub_a = generate_rsa_keypair()
        self.org_a = Organisation.objects.create(
            user=self.user_a, name='Hospital A DP Test', organisation_type='hospital',
            location='Korle Bu', public_key=pub_a, private_key=priv_a,
        )
        Patient.objects.create(
            organisation=self.org_a, patient_id='DP001', name='Patient One',
            age=50, gender='M', phone_number='0244000002',
            diagnosis='Diabetes', medication='Metformin',
        )
        self.token_a = self.client.post(
            '/api/token/', {'username': 'hospA_dp_test', 'password': 'testpass123'}
        ).data['access']

    def auth_header(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def test_compute_endpoint_returns_noisy_count_locally(self):
        """The compute endpoint runs entirely locally, no mocking needed."""
        response = self.client.post(
            '/api/privacy/differential-privacy/compute/',
            {'query_type': 'count_by_diagnosis', 'diagnosis': 'Diabetes'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('noisy_result', response.data)
        self.assertIn('epsilon', response.data)

    @patch('privacy.views.requests.post')
    def test_query_view_calls_target_server_and_returns_result(self, mock_post):
        mock_post.return_value = Mock(status_code=200, json=lambda: {
            'target_organisation': 'Remote Hospital', 'query_type': 'count_by_diagnosis',
            'result_label': 'Noisy count', 'noisy_result': 3, 'epsilon': 1.0,
            'note': 'test note',
        })
        mock_post.return_value.raise_for_status = lambda: None

        response = self.client.post(
            '/api/privacy/differential-privacy/query/',
            {'target_url': 'http://127.0.0.1:9999', 'query_type': 'count_by_diagnosis', 'diagnosis': 'Diabetes'},
            **self.auth_header(self.token_a)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['noisy_result'], 3)
        mock_post.assert_called_once()