
from django.db import models
from organisations.models import Organisation
from patients.models import Patient


class PrivacyResult(models.Model):
    TECHNIQUE_CHOICES = [
        ('encryption', 'Fernet Encryption'),
        ('anonymization', 'Anonymization'),
        ('masking', 'Data Masking'),
        ('differential_privacy', 'Differential Privacy'),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='privacy_results')
    technique = models.CharField(max_length=50, choices=TECHNIQUE_CHOICES)
    original_record_count = models.IntegerField()
    processed_record_count = models.IntegerField()
    processing_time_seconds = models.FloatField()
    utility_score = models.FloatField(help_text="Data utility preserved after privacy technique (0-1)")
    privacy_score = models.FloatField(help_text="Privacy strength of the technique (0-1)")
    output_sample = models.JSONField(blank=True, null=True, help_text="Sample of processed output")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.organisation.name} - {self.technique} - {self.created_at.date()}"



class SharedEncryptedRecord(models.Model):
    """Stored on the RECEIVER's server only. Sender info is plain data, not a FK, since sender lives on a different server/database entirely."""

    sender_name = models.CharField(max_length=255)
    sender_url = models.URLField(help_text="Base URL of the sender's server, e.g. http://127.0.0.1:8000")
    patient_id_reference = models.CharField(max_length=100)

    encrypted_payload = models.TextField(help_text="AES-encrypted patient data")
    encrypted_session_key = models.TextField(help_text="RSA-encrypted one-time session key")
    signature = models.TextField(help_text="Sender's digital signature over the plaintext")

    is_decrypted = models.BooleanField(default=False)
    signature_verified = models.BooleanField(null=True, blank=True)
    decrypted_at = models.DateTimeField(null=True, blank=True)
    decrypted_payload = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"From {self.sender_name} ({self.patient_id_reference})"

        

class AnonymizedDataset(models.Model):
    """A bulk export of anonymized patient data received from another organisation."""

    sender_name = models.CharField(max_length=255)
    sender_url = models.URLField()
    filter_criteria = models.CharField(max_length=255, help_text="e.g. 'diagnosis=Hypertension'")
    record_count = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"From {self.sender_name} ({self.record_count} records)"


class AnonymizedRecord(models.Model):
    """A single anonymized row belonging to an AnonymizedDataset."""

    dataset = models.ForeignKey(AnonymizedDataset, on_delete=models.CASCADE, related_name='records')
    anonymized_label = models.CharField(max_length=100)
    age_range = models.CharField(max_length=20)
    gender = models.CharField(max_length=1)
    diagnosis = models.CharField(max_length=255)
    medication = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.anonymized_label} ({self.dataset_id})"