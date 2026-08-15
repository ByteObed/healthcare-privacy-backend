
from rest_framework import serializers
from .models import (
    PrivacyResult,
    SharedEncryptedRecord,
    AnonymizedDataset,
    AnonymizedRecord,
)


class PrivacyResultSerializer(serializers.ModelSerializer):
    organisation_name = serializers.SerializerMethodField()
    technique_display = serializers.SerializerMethodField()

    class Meta:
        model = PrivacyResult
        fields = [
            'id', 'organisation_name', 'technique', 'technique_display',
            'original_record_count', 'processed_record_count',
            'processing_time_seconds', 'utility_score', 'privacy_score',
            'output_sample', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_organisation_name(self, obj):
        return obj.organisation.name

    def get_technique_display(self, obj):
        return obj.get_technique_display()


class PrivacyResultSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for dashboard/comparison views"""
    technique_display = serializers.SerializerMethodField()

    class Meta:
        model = PrivacyResult
        fields = [
            'id', 'technique', 'technique_display',
            'processing_time_seconds', 'utility_score',
            'privacy_score', 'created_at'
        ]

    def get_technique_display(self, obj):
        return obj.get_technique_display()


# --- Encryption / SharedEncryptedRecord ---

class SendEncryptedRecordSerializer(serializers.Serializer):
    """Sender's request: which local patient, and which receiver server to send to."""
    patient_id = serializers.CharField()
    receiver_url = serializers.URLField(help_text="e.g. http://127.0.0.1:8001")


class SharedEncryptedRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SharedEncryptedRecord
        fields = [
            'id', 'sender_name', 'sender_url', 'patient_id_reference',
            'encrypted_payload', 'is_decrypted', 'signature_verified',
            'decrypted_at', 'decrypted_payload', 'created_at'
        ]
        read_only_fields = fields


# --- Anonymization ---

class AnonymizedRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnonymizedRecord
        fields = ['id', 'anonymized_label', 'age_range', 'gender', 'diagnosis', 'medication']


class AnonymizedDatasetSerializer(serializers.ModelSerializer):
    records = AnonymizedRecordSerializer(many=True, read_only=True)

    class Meta:
        model = AnonymizedDataset
        fields = ['id', 'sender_name', 'sender_url', 'filter_criteria', 'record_count', 'created_at', 'records']
        read_only_fields = fields


class ExportAnonymizedDatasetSerializer(serializers.Serializer):
    """Used when Hospital A exports an anonymized dataset to another hospital's server."""
    receiver_url = serializers.URLField(help_text="e.g. http://127.0.0.1:8001")
    diagnosis_filter = serializers.CharField(required=False, allow_blank=True)

# --- Masking ---

class MaskedPatientSerializer(serializers.Serializer):
    """Used for masked display view — not tied to a model, transformation only."""
    patient_id = serializers.CharField()
    name = serializers.CharField()
    diagnosis = serializers.CharField()
    masked_phone = serializers.CharField(required=False)


# --- Differential Privacy ---

class DifferentialPrivacyQuerySerializer(serializers.Serializer):
    """Used when Hospital B queries another hospital's server for an aggregate stat."""
    target_url = serializers.URLField(help_text="e.g. http://127.0.0.1:8000")
    query_type = serializers.ChoiceField(choices=['count_by_diagnosis', 'count_by_gender', 'average_age'])
    diagnosis = serializers.CharField(required=False, allow_blank=True)


class DifferentialPrivacyComputeSerializer(serializers.Serializer):
    """Internal server-to-server request: compute this query locally and return the noisy result."""
    query_type = serializers.ChoiceField(choices=['count_by_diagnosis', 'count_by_gender', 'average_age'])
    diagnosis = serializers.CharField(required=False, allow_blank=True)