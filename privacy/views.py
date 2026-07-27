
import time
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
    DecryptRecordSerializer,
    AnonymizedDatasetSerializer, 
    ExportAnonymizedDatasetSerializer,
    MaskedPatientSerializer,
    DifferentialPrivacyQuerySerializer
)
from .utils import (
    generate_fernet_key,
    encrypt_patient_record, 
    decrypt_patient_record, 
    anonymize_patient_records, 
    mask_name, mask_patient_id, 
    mask_phone_number, 
    apply_differential_privacy_count, 
    apply_differential_privacy_mean

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
    """Hospital A encrypts one patient record and sends it to Hospital B."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SendEncryptedRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = request.user.organisation
        patient_id = serializer.validated_data['patient_id']
        receiver_id = serializer.validated_data['receiver_id']

        try:
            patient = Patient.objects.get(patient_id=patient_id, organisation=sender)
        except Patient.DoesNotExist:
            return Response({"error": "Patient not found in your organisation."}, status=status.HTTP_404_NOT_FOUND)

        try:
            receiver = Organisation.objects.get(id=receiver_id)
        except Organisation.DoesNotExist:
            return Response({"error": "Receiving organisation not found."}, status=status.HTTP_404_NOT_FOUND)

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

        key = generate_fernet_key()
        encrypted_payload = encrypt_patient_record(patient_data, key)

        processing_time = time.time() - start_time

        shared_record = SharedEncryptedRecord.objects.create(
            sender=sender,
            receiver=receiver,
            patient_id_reference=patient.patient_id,
            encrypted_payload=encrypted_payload,
            encryption_key=key,
        )

        # Log this operation for the comparison dashboard
        PrivacyResult.objects.create(
            organisation=sender,
            technique='encryption',
            original_record_count=1,
            processed_record_count=1,
            processing_time_seconds=processing_time,
            utility_score=1.0,  # Encryption preserves 100% utility once decrypted
            privacy_score=0.9,  # Strong privacy, but reversible if key is leaked
            output_sample={"encrypted_preview": encrypted_payload[:60] + "..."},
        )

        return Response(
            SharedEncryptedRecordSerializer(shared_record).data,
            status=status.HTTP_201_CREATED
        )

class SentEncryptedRecordsListView(generics.ListAPIView):
    """Hospital A views encrypted records it has sent to other organisations."""
    serializer_class = SharedEncryptedRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def get_queryset(self):
        return SharedEncryptedRecord.objects.filter(sender=self.request.user.organisation)        


class ReceivedEncryptedRecordsListView(generics.ListAPIView):
    """Hospital B views encrypted records sent to them, awaiting decryption."""
    serializer_class = SharedEncryptedRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def get_queryset(self):
        return SharedEncryptedRecord.objects.filter(receiver=self.request.user.organisation)


class DecryptRecordView(APIView):
    """Hospital B submits the key to decrypt a received record (server-side decryption)."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def post(self, request, pk):
        try:
            shared_record = SharedEncryptedRecord.objects.get(
                pk=pk, receiver=request.user.organisation
            )
        except SharedEncryptedRecord.DoesNotExist:
            return Response({"error": "Record not found."}, status=status.HTTP_404_NOT_FOUND)

        if shared_record.is_decrypted:
            return Response(
                {"message": "Already decrypted.", "data": shared_record.decrypted_payload},
                status=status.HTTP_200_OK
            )

        serializer = DecryptRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submitted_key = serializer.validated_data['encryption_key']

        if submitted_key != shared_record.encryption_key:
            return Response({"error": "Incorrect decryption key."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decrypted_data = decrypt_patient_record(shared_record.encrypted_payload, submitted_key)
        except Exception:
            return Response({"error": "Decryption failed."}, status=status.HTTP_400_BAD_REQUEST)

        from django.utils import timezone
        shared_record.is_decrypted = True
        shared_record.decrypted_at = timezone.now()
        shared_record.decrypted_payload = decrypted_data
        shared_record.save()

        # Create the real Patient record under Hospital B now that data is decrypted
        Patient.objects.create(
            organisation=request.user.organisation,
            patient_id=decrypted_data['patient_id'],
            name=decrypted_data['name'],
            age=decrypted_data['age'],
            gender=decrypted_data['gender'],
            phone_number=decrypted_data['phone_number'],
            diagnosis=decrypted_data['diagnosis'],
            medication=decrypted_data['medication'],
        )

        return Response(SharedEncryptedRecordSerializer(shared_record).data, status=status.HTTP_200_OK)

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
    """Hospital A exports a filtered, anonymized dataset to Hospital B."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def post(self, request):
        serializer = ExportAnonymizedDatasetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = request.user.organisation
        receiver_id = serializer.validated_data['receiver_id']
        diagnosis_filter = serializer.validated_data.get('diagnosis_filter', '')

        try:
            receiver = Organisation.objects.get(id=receiver_id)
        except Organisation.DoesNotExist:
            return Response({"error": "Receiving organisation not found."}, status=status.HTTP_404_NOT_FOUND)

        patients_qs = Patient.objects.filter(organisation=sender)
        if diagnosis_filter:
            patients_qs = patients_qs.filter(diagnosis__iexact=diagnosis_filter)

        if not patients_qs.exists():
            return Response({"error": "No matching patients found to export."}, status=status.HTTP_404_NOT_FOUND)

        start_time = time.time()
        anonymized_records = anonymize_patient_records(patients_qs)
        processing_time = time.time() - start_time

        dataset = AnonymizedDataset.objects.create(
            sender=sender,
            receiver=receiver,
            filter_criteria=f"diagnosis={diagnosis_filter}" if diagnosis_filter else "all",
            record_count=len(anonymized_records),
        )

        for record in anonymized_records:
            AnonymizedRecord.objects.create(dataset=dataset, **record)

        # Log for the comparison dashboard
        PrivacyResult.objects.create(
            organisation=sender,
            technique='anonymization',
            original_record_count=patients_qs.count(),
            processed_record_count=len(anonymized_records),
            processing_time_seconds=processing_time,
            utility_score=0.75,  # Some utility lost — exact age/identity gone, ranges/categories remain
            privacy_score=0.85,  # Strong privacy, but theoretically vulnerable to re-identification attacks
            output_sample={"sample": anonymized_records[:2]},
        )

        return Response(AnonymizedDatasetSerializer(dataset).data, status=status.HTTP_201_CREATED)


class SentAnonymizedDatasetsListView(generics.ListAPIView):
    """Hospital A views anonymized datasets it has sent to other organisations."""
    serializer_class = AnonymizedDatasetSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def get_queryset(self):
        return AnonymizedDataset.objects.filter(sender=self.request.user.organisation)
        

class ReceivedAnonymizedDatasetsListView(generics.ListAPIView):
    """Hospital B views anonymized datasets received from other organisations."""
    serializer_class = AnonymizedDatasetSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def get_queryset(self):
        return AnonymizedDataset.objects.filter(receiver=self.request.user.organisation)



###       Add this view alongside your existing encryption views 

class RetrieveEncryptionKeyView(APIView):
    """Hospital B retrieves the decryption key through a separate, one-time-use endpoint."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def get(self, request, pk):
        try:
            shared_record = SharedEncryptedRecord.objects.get(
                pk=pk, receiver=request.user.organisation
            )
        except SharedEncryptedRecord.DoesNotExist:
            return Response({"error": "Record not found."}, status=status.HTTP_404_NOT_FOUND)

        if shared_record.key_retrieved:
            return Response(
                {"error": "Key has already been retrieved and is no longer available via this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )

        shared_record.key_retrieved = True
        shared_record.save()

        return Response({"encryption_key": shared_record.encryption_key}, status=status.HTTP_200_OK)        


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


###

class DifferentialPrivacyQueryView(APIView):
    """Hospital B queries Hospital A's aggregate stats and receives a noisy result."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    
    def post(self, request):
        serializer = DifferentialPrivacyQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_organisation_id = serializer.validated_data['target_organisation_id']
        query_type = serializer.validated_data['query_type']
        diagnosis = serializer.validated_data.get('diagnosis', '')

        try:
            target_org = Organisation.objects.get(id=target_organisation_id)
        except Organisation.DoesNotExist:
            return Response({"error": "Target organisation not found."}, status=status.HTTP_404_NOT_FOUND)

        epsilon = 1.0  # Privacy budget used for this query

        start_time = time.time()
        patients_qs = Patient.objects.filter(organisation=target_org)

        if query_type == 'count_by_diagnosis':
            if not diagnosis:
                return Response({"error": "diagnosis field is required for this query_type."}, status=status.HTTP_400_BAD_REQUEST)
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
            return Response({"error": "Invalid query_type."}, status=status.HTTP_400_BAD_REQUEST)

        processing_time = time.time() - start_time

        PrivacyResult.objects.create(
            organisation=request.user.organisation,
            technique='differential_privacy',
            original_record_count=patients_qs.count(),
            processed_record_count=1,
            processing_time_seconds=processing_time,
            utility_score=0.6,
            privacy_score=0.95,
            output_sample={"result_label": result_label, "noisy_value": noisy_value, "epsilon": epsilon},
        )

        return Response({
            "target_organisation": target_org.name,
            "query_type": query_type,
            "result_label": result_label,
            "noisy_result": noisy_value,
            "epsilon": epsilon,
            "note": f"This value contains statistical noise (Laplace mechanism, epsilon={epsilon}) and does not reveal exact record-level data.",
        }, status=status.HTTP_200_OK)