
import time
import requests
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from organisations.models import Organisation
from organisations.permissions import IsOrganisationUser
from patients.models import Patient
from django.db.models import Count, Avg
from .models import PrivacyResult, SharedEncryptedRecord, AnonymizedDataset, AnonymizedRecord
from .serializers import (
    PrivacyResultSerializer,
    PrivacyResultSummarySerializer,
    SendEncryptedRecordSerializer,
    SharedEncryptedRecordSerializer,
    AnonymizedDatasetSerializer, 
    ExportAnonymizedDatasetSerializer,
    MaskedPatientSerializer,
    DifferentialPrivacyQuerySerializer,
    DifferentialPrivacyComputeSerializer,
)
from .utils import (
    generate_session_key,
    encrypt_data_with_session_key,
    decrypt_data_with_session_key,
    encrypt_session_key_with_public_key,
    decrypt_session_key_with_private_key,
    sign_data,
    verify_signature,
    anonymize_patient_records,
    mask_name,
    mask_patient_id,
    mask_phone_number,
    apply_differential_privacy_count,
    apply_differential_privacy_mean,
)

class PrivacyResultListView(generics.ListAPIView):
    serializer_class = PrivacyResultSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]
    filterset_fields = ['technique']
    ordering_fields = ['created_at', 'utility_score', 'privacy_score']

    def get_queryset(self):
        return PrivacyResult.objects.filter(organisation=self.request.user.organisation)



class PrivacyComparisonView(generics.ListAPIView):
    serializer_class = PrivacyResultSummarySerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]
    filterset_fields = ['technique']
    ordering_fields = ['utility_score', 'privacy_score', 'processing_time_seconds']
    pagination_class = None  # comparison dashboard needs the full dataset, not a page

    def get_queryset(self):
        return PrivacyResult.objects.all().order_by('-created_at')


# --- ENCRYPTION ---

class SendEncryptedRecordView(APIView):
    """SENDER side: encrypts a local patient record and POSTs it to the receiver's own server."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def post(self, request):
        serializer = SendEncryptedRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender_org = request.user.organisation
        patient_id = serializer.validated_data['patient_id']
        receiver_url = serializer.validated_data['receiver_url'].rstrip('/')

        try:
            patient = Patient.objects.get(patient_id=patient_id, organisation=sender_org)
        except Patient.DoesNotExist:
            return Response({"error": "Patient not found in your organisation."}, status=404)

        try:
            key_response = requests.get(f"{receiver_url}/api/organisations/public-key/", timeout=5)
            key_response.raise_for_status()
            receiver_public_key = key_response.json()['public_key']
            receiver_name = key_response.json()['organisation_name']
        except Exception as e:
            return Response({"error": f"Could not reach receiver server or fetch its public key: {str(e)}"}, status=502)

        start_time = time.time()

        patient_data = {
            "patient_id": patient.patient_id,
            "name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "phone_number": patient.phone_number,
            "diagnosis": patient.diagnosis,
            "medication": patient.medication,
        }

        session_key = generate_session_key()
        encrypted_payload = encrypt_data_with_session_key(patient_data, session_key)
        encrypted_session_key = encrypt_session_key_with_public_key(session_key, receiver_public_key)
        signature = sign_data(patient_data, sender_org.private_key)

        processing_time = time.time() - start_time

        payload = {
            "sender_name": sender_org.name,
            "sender_url": request.build_absolute_uri('/').rstrip('/'),
            "patient_id_reference": patient.patient_id,
            "encrypted_payload": encrypted_payload,
            "encrypted_session_key": encrypted_session_key,
            "signature": signature,
        }

        try:
            send_response = requests.post(f"{receiver_url}/api/privacy/encryption/receive/", json=payload, timeout=5)
            send_response.raise_for_status()
        except Exception as e:
            return Response({"error": f"Failed to deliver record to receiver: {str(e)}"}, status=502)

        PrivacyResult.objects.create(
            organisation=sender_org,
            technique='encryption',
            original_record_count=1,
            processed_record_count=1,
            processing_time_seconds=processing_time,
            utility_score=1.0,
            privacy_score=0.95,
            output_sample={"sent_to": receiver_name, "receiver_url": receiver_url},
        )

        return Response({"message": f"Encrypted record sent to {receiver_name} successfully."}, status=201)



class SentEncryptedRecordsListView(generics.ListAPIView):
    """Hospital A views encrypted records it has sent to other organisations."""
    serializer_class = SharedEncryptedRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def get_queryset(self):
        return SharedEncryptedRecord.objects.filter(sender=self.request.user.organisation)        


class ReceivedEncryptedRecordsListView(generics.ListAPIView):
    """This server's organisation views all encrypted records it has received."""
    serializer_class = SharedEncryptedRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]
    queryset = SharedEncryptedRecord.objects.all()

    

class DecryptRecordView(APIView):
    """RECEIVER decrypts a record using ITS OWN private key (never left this server), then verifies the sender's signature."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def post(self, request, pk):
        try:
            record = SharedEncryptedRecord.objects.get(pk=pk)
        except SharedEncryptedRecord.DoesNotExist:
            return Response({"error": "Record not found."}, status=404)

        if record.is_decrypted:
            return Response({"message": "Already decrypted.", "data": record.decrypted_payload}, status=200)

        receiver_org = request.user.organisation

        try:
            session_key = decrypt_session_key_with_private_key(record.encrypted_session_key, receiver_org.private_key)
            decrypted_data = decrypt_data_with_session_key(record.encrypted_payload, session_key)
        except Exception as e:
            return Response({"error": f"Decryption failed: {str(e)}"}, status=400)

        signature_valid = False
        try:
            key_response = requests.get(f"{record.sender_url}/api/organisations/public-key/", timeout=5)
            sender_public_key = key_response.json()['public_key']
            signature_valid = verify_signature(decrypted_data, record.signature, sender_public_key)
        except Exception:
            signature_valid = False

        from django.utils import timezone
        record.is_decrypted = True
        record.decrypted_at = timezone.now()
        record.decrypted_payload = decrypted_data
        record.signature_verified = signature_valid
        record.save()

        Patient.objects.update_or_create(
            organisation=receiver_org,
            patient_id=decrypted_data['patient_id'],
            defaults={
                'name': decrypted_data['name'],
                'age': decrypted_data['age'],
                'gender': decrypted_data['gender'],
                'phone_number': decrypted_data.get('phone_number', '0000000000'),
                'diagnosis': decrypted_data['diagnosis'],
                'medication': decrypted_data['medication'],
            }
        )

        return Response(SharedEncryptedRecordSerializer(record).data, status=200)

        
class RegenerateEncryptionKeyView(APIView):
    """Sender regenerates a fresh key for a record whose key was retrieved but never used to decrypt."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def post(self, request, pk):
        try:
            shared_record = SharedEncryptedRecord.objects.get(
                pk=pk, sender=request.user.organisation
            )
        except SharedEncryptedRecord.DoesNotExist:
            return Response({"error": "Record not found."}, status=status.HTTP_404_NOT_FOUND)

        if shared_record.is_decrypted:
            return Response(
                {"error": "This record has already been decrypted."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            patient = Patient.objects.get(
                patient_id=shared_record.patient_id_reference,
                organisation=request.user.organisation
            )
        except Patient.DoesNotExist:
            return Response(
                {"error": "Original patient record no longer exists."},
                status=status.HTTP_404_NOT_FOUND
            )

        patient_data = {
            "patient_id": patient.patient_id,
            "name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "phone_number": patient.phone_number,
            "diagnosis": patient.diagnosis,
            "medication": patient.medication,
        }

        new_key = generate_fernet_key()
        new_encrypted_payload = encrypt_patient_record(patient_data, new_key)

        shared_record.encrypted_payload = new_encrypted_payload
        shared_record.encryption_key = new_key
        shared_record.key_retrieved = False
        shared_record.save()

        return Response(
            SharedEncryptedRecordSerializer(shared_record).data,
            status=status.HTTP_200_OK
        )        


# --- ANONYMIZATION, MASKING, DIFFERENTIAL PRIVACY (placeholders, built next) ---


class ExportAnonymizedDatasetView(APIView):
    """SENDER side: filters, strips identity, and POSTs the anonymized dataset to the receiver's own server."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def post(self, request):
        serializer = ExportAnonymizedDatasetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender_org = request.user.organisation
        receiver_url = serializer.validated_data['receiver_url'].rstrip('/')
        diagnosis_filter = serializer.validated_data.get('diagnosis_filter', '')

        patients_qs = Patient.objects.filter(organisation=sender_org)
        if diagnosis_filter:
            patients_qs = patients_qs.filter(diagnosis__iexact=diagnosis_filter)

        if not patients_qs.exists():
            return Response({"error": "No matching patients found to export."}, status=404)

        # Confirm the receiver server is reachable and get its name
        try:
            info_response = requests.get(f"{receiver_url}/api/organisations/public-key/", timeout=5)
            info_response.raise_for_status()
            receiver_name = info_response.json()['organisation_name']
        except Exception as e:
            return Response({"error": f"Could not reach receiver server: {str(e)}"}, status=502)

        start_time = time.time()
        anonymized_records = anonymize_patient_records(patients_qs)
        processing_time = time.time() - start_time

        payload = {
            "sender_name": sender_org.name,
            "sender_url": request.build_absolute_uri('/').rstrip('/'),
            "filter_criteria": f"diagnosis={diagnosis_filter}" if diagnosis_filter else "all",
            "records": anonymized_records,
        }

        try:
            send_response = requests.post(f"{receiver_url}/api/privacy/anonymization/receive/", json=payload, timeout=5)
            send_response.raise_for_status()
        except Exception as e:
            return Response({"error": f"Failed to deliver dataset to receiver: {str(e)}"}, status=502)

        PrivacyResult.objects.create(
            organisation=sender_org,
            technique='anonymization',
            original_record_count=patients_qs.count(),
            processed_record_count=len(anonymized_records),
            processing_time_seconds=processing_time,
            utility_score=0.75,
            privacy_score=0.85,
            output_sample={"sent_to": receiver_name, "sample": anonymized_records[:2]},
        )

        return Response({"message": f"Anonymized dataset ({len(anonymized_records)} records) sent to {receiver_name}."}, status=201)


class ReceiveAnonymizedDatasetView(APIView):
    """RECEIVER side: accepts an incoming anonymized dataset from another server. No auth — server-to-server delivery."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        required = ['sender_name', 'sender_url', 'filter_criteria', 'records']
        if not all(field in request.data for field in required):
            return Response({"error": "Missing required fields."}, status=400)

        dataset = AnonymizedDataset.objects.create(
            sender_name=request.data['sender_name'],
            sender_url=request.data['sender_url'],
            filter_criteria=request.data['filter_criteria'],
            record_count=len(request.data['records']),
        )

        for record in request.data['records']:
            AnonymizedRecord.objects.create(dataset=dataset, **record)

        return Response({"message": "Dataset received.", "id": dataset.id}, status=201)


class ReceivedAnonymizedDatasetsListView(generics.ListAPIView):
    """This server's organisation views all anonymized datasets it has received."""
    serializer_class = AnonymizedDatasetSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]
    queryset = AnonymizedDataset.objects.all()


###       Add this view alongside your existing encryption views 


class ReceiveEncryptedRecordView(APIView):
    """RECEIVER side: accepts an incoming encrypted record from another server. No auth — this is a server-to-server delivery endpoint."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        required = ['sender_name', 'sender_url', 'patient_id_reference', 'encrypted_payload', 'encrypted_session_key', 'signature']
        if not all(field in request.data for field in required):
            return Response({"error": "Missing required fields."}, status=400)

        record = SharedEncryptedRecord.objects.create(
            sender_name=request.data['sender_name'],
            sender_url=request.data['sender_url'],
            patient_id_reference=request.data['patient_id_reference'],
            encrypted_payload=request.data['encrypted_payload'],
            encrypted_session_key=request.data['encrypted_session_key'],
            signature=request.data['signature'],
        )
        return Response({"message": "Record received.", "id": record.id}, status=201)

# Masking

class MaskedPatientListView(APIView):
    """Returns Hospital A's own patients with name, patient_id, and phone masked — a display-layer transformation only."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def get(self, request):
        start_time = time.time()

        patients = Patient.objects.filter(organisation=request.user.organisation)

        masked_data = []
        for p in patients:
            masked_data.append({
                "patient_id": mask_patient_id(p.patient_id),
                "name": mask_name(p.name),
                "diagnosis": p.diagnosis,  # not masked, demonstrates selective field masking
                "masked_phone": mask_phone_number(p.phone_number),
            })

        processing_time = time.time() - start_time

       

        serializer = MaskedPatientSerializer(masked_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ApplyMaskingLogView(APIView):
    """Explicitly apply masking to current raw patient data and log ONE comparison result."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def post(self, request):
        start_time = time.time()

        patients = Patient.objects.filter(organisation=request.user.organisation)

        if not patients.exists():
            return Response({"error": "No patient data available to mask. Add or import patients first."}, status=status.HTTP_404_NOT_FOUND)

        masked_data = []
        for p in patients:
            masked_data.append({
                "patient_id": mask_patient_id(p.patient_id),
                "name": mask_name(p.name),
                "diagnosis": p.diagnosis,
                "masked_phone": mask_phone_number(p.phone_number),
            })

        processing_time = time.time() - start_time

        result = PrivacyResult.objects.create(
            organisation=request.user.organisation,
            technique='masking',
            original_record_count=patients.count(),
            processed_record_count=len(masked_data),
            processing_time_seconds=processing_time,
            utility_score=0.9,
            privacy_score=0.5,
            output_sample={"sample": masked_data[:2]},
        )

        return Response({
            "message": f"Masking applied to {len(masked_data)} patient records and logged for comparison.",
            "result_id": result.id,
        }, status=status.HTTP_201_CREATED)        


###

class DifferentialPrivacyQueryView(APIView):
    """REQUESTER side: asks another hospital's server to compute a noisy aggregate."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def post(self, request):
        serializer = DifferentialPrivacyQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_url = serializer.validated_data['target_url'].rstrip('/')
        query_type = serializer.validated_data['query_type']
        diagnosis = serializer.validated_data.get('diagnosis', '')

        payload = {"query_type": query_type, "diagnosis": diagnosis}

        try:
            compute_response = requests.post(f"{target_url}/api/privacy/differential-privacy/compute/", json=payload, timeout=5)
            compute_response.raise_for_status()
            result = compute_response.json()
        except Exception as e:
            return Response({"error": f"Could not reach target server: {str(e)}"}, status=502)

        # Log this from the REQUESTER's side too
        PrivacyResult.objects.create(
            organisation=request.user.organisation,
            technique='differential_privacy',
            original_record_count=0,  # requester never sees the raw count, by design
            processed_record_count=1,
            processing_time_seconds=result.get('processing_time_seconds', 0),
            utility_score=0.6,
            privacy_score=0.95,
            output_sample={"queried": target_url, "result": result},
        )

        return Response(result, status=200)


class DifferentialPrivacyComputeView(APIView):
    """RESPONDER side: computes the noisy aggregate using THIS server's own local data. No auth — server-to-server query, raw data never leaves this server."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = DifferentialPrivacyComputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        query_type = serializer.validated_data['query_type']
        diagnosis = serializer.validated_data.get('diagnosis', '')

        organisation = Organisation.objects.first()
        if not organisation:
            return Response({"error": "No organisation registered on this server."}, status=404)

        epsilon = 1.0
        start_time = time.time()
        patients_qs = Patient.objects.filter(organisation=organisation)

        if query_type == 'count_by_diagnosis':
            if not diagnosis:
                return Response({"error": "diagnosis is required for this query_type."}, status=400)
            true_value = patients_qs.filter(diagnosis__iexact=diagnosis).count()
            noisy_value = apply_differential_privacy_count(true_value, epsilon=epsilon)
            result_label = f"Noisy count of patients with diagnosis '{diagnosis}'"

        elif query_type == 'count_by_gender':
            true_value = patients_qs.count()
            noisy_value = apply_differential_privacy_count(true_value, epsilon=epsilon)
            result_label = "Noisy total patient count"

        elif query_type == 'average_age':
            avg_result = patients_qs.aggregate(avg_age=Avg('age'))
            true_value = avg_result['avg_age'] or 0
            noisy_value = apply_differential_privacy_mean(true_value, epsilon=epsilon)
            result_label = "Noisy average patient age"

        else:
            return Response({"error": "Invalid query_type."}, status=400)

        processing_time = time.time() - start_time

        # Log this from the RESPONDER's side too — someone queried us
        PrivacyResult.objects.create(
            organisation=organisation,
            technique='differential_privacy',
            original_record_count=patients_qs.count(),
            processed_record_count=1,
            processing_time_seconds=processing_time,
            utility_score=0.6,
            privacy_score=0.95,
            output_sample={"result_label": result_label, "noisy_value": noisy_value, "epsilon": epsilon},
        )

        return Response({
            "target_organisation": organisation.name,
            "query_type": query_type,
            "result_label": result_label,
            "noisy_result": noisy_value,
            "epsilon": epsilon,
            "processing_time_seconds": processing_time,
            "note": f"This value contains statistical noise (Laplace mechanism, epsilon={epsilon}) and does not reveal exact record-level data.",
        }, status=200)