
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


# --- Encryption ---

class SendEncryptedRecordSerializer(serializers.Serializer):
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


class SentEncryptedRecordSerializer(serializers.ModelSerializer):
    sent_to = serializers.SerializerMethodField()

    class Meta:
        model = PrivacyResult
        fields = ['id', 'sent_to', 'processing_time_seconds', 'created_at']

    def get_sent_to(self, obj):
        return obj.output_sample.get('sent_to') if obj.output_sample else None


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
    receiver_url = serializers.URLField(help_text="e.g. http://127.0.0.1:8001")
    diagnosis_filter = serializers.CharField(required=False, allow_blank=True)


# privacy/serializers.py

class SentAnonymizedDatasetSerializer(serializers.ModelSerializer):
    sent_to = serializers.SerializerMethodField()
    records = serializers.SerializerMethodField()

    class Meta:
        model = PrivacyResult  # ← MUST BE PrivacyResult, not AnonymizedDataset
        fields = ['id', 'sent_to', 'original_record_count', 'processed_record_count', 'processing_time_seconds', 'records', 'created_at']

    def get_sent_to(self, obj):
        return obj.output_sample.get('sent_to') if obj.output_sample else None

    def get_records(self, obj):
        return obj.output_sample.get('records', []) if obj.output_sample else []


# --- Masking ---

class MaskedPatientSerializer(serializers.Serializer):
    patient_id = serializers.CharField()
    name = serializers.CharField()
    diagnosis = serializers.CharField()
    masked_phone = serializers.CharField(required=False)


# --- Differential Privacy ---

class DifferentialPrivacyQuerySerializer(serializers.Serializer):
    target_url = serializers.URLField(help_text="e.g. http://127.0.0.1:8000")
    query_type = serializers.ChoiceField(choices=['count_by_diagnosis', 'count_by_gender', 'average_age'])
    diagnosis = serializers.CharField(required=False, allow_blank=True)


class DifferentialPrivacyComputeSerializer(serializers.Serializer):
    query_type = serializers.ChoiceField(choices=['count_by_diagnosis', 'count_by_gender', 'average_age'])
    diagnosis = serializers.CharField(required=False, allow_blank=True)