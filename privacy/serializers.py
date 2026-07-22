
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
    """Used when Hospital A sends an encrypted record to Hospital B."""
    patient_id = serializers.CharField()
    receiver_id = serializers.IntegerField()


class SharedEncryptedRecordSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()

    class Meta:
        model = SharedEncryptedRecord
        fields = [
            'id', 'sender_name', 'receiver_name', 'patient_id_reference',
            'encrypted_payload', 'key_retrieved', 'is_decrypted', 'decrypted_at',
            'decrypted_payload', 'created_at'
        ]
        read_only_fields = fields

    def get_sender_name(self, obj):
        return obj.sender.name

    def get_receiver_name(self, obj):
        return obj.receiver.name

class DecryptRecordSerializer(serializers.Serializer):
    """Used when Hospital B submits the key to decrypt a record."""
    encryption_key = serializers.CharField()


# --- Anonymization ---

class AnonymizedRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnonymizedRecord
        fields = ['id', 'anonymized_label', 'age_range', 'gender', 'diagnosis', 'medication']


class AnonymizedDatasetSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()
    records = AnonymizedRecordSerializer(many=True, read_only=True)

    class Meta:
        model = AnonymizedDataset
        fields = [
            'id', 'sender_name', 'receiver_name', 'filter_criteria',
            'record_count', 'created_at', 'records'
        ]
        read_only_fields = ['record_count', 'created_at']

    def get_sender_name(self, obj):
        return obj.sender.name

    def get_receiver_name(self, obj):
        return obj.receiver.name


class ExportAnonymizedDatasetSerializer(serializers.Serializer):
    """Used when Hospital A exports an anonymized dataset to Hospital B."""
    receiver_id = serializers.IntegerField()
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
    """Used when Hospital B queries Hospital A's aggregate stats."""
    target_organisation_id = serializers.IntegerField()
    query_type = serializers.ChoiceField(choices=['count_by_diagnosis', 'count_by_gender', 'average_age'])
    diagnosis = serializers.CharField(required=False, allow_blank=True)