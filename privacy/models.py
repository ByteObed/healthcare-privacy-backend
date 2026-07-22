
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
    sender = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='sent_encrypted_records')
    receiver = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='received_encrypted_records')
    patient_id_reference = models.CharField(max_length=100, help_text="Original patient_id at sender side, for reference")

    encrypted_payload = models.TextField(help_text="Fernet-encrypted JSON of the patient record")
    encryption_key = models.CharField(max_length=255, help_text="Fernet key needed to decrypt this payload")
    key_retrieved = models.BooleanField(default=False, help_text="True once receiver has fetched the key via the dedicated endpoint")

    is_decrypted = models.BooleanField(default=False)
    decrypted_at = models.DateTimeField(null=True, blank=True)
    decrypted_payload = models.JSONField(null=True, blank=True, help_text="Plaintext patient data after decryption")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.name} -> {self.receiver.name} ({self.patient_id_reference})"

    def __str__(self):
        return f"{self.sender.name} -> {self.receiver.name} ({self.patient_id_reference})"


class AnonymizedDataset(models.Model):
    """A bulk export of anonymized patient data shared from one organisation to another."""

    sender = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='sent_anonymized_datasets')
    receiver = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='received_anonymized_datasets')
    filter_criteria = models.CharField(max_length=255, help_text="e.g. 'diagnosis=Hypertension'")
    record_count = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.name} -> {self.receiver.name} ({self.record_count} records)"


class AnonymizedRecord(models.Model):
    """A single anonymized row belonging to an AnonymizedDataset."""

    dataset = models.ForeignKey(AnonymizedDataset, on_delete=models.CASCADE, related_name='records')
    anonymized_label = models.CharField(max_length=100, help_text="e.g. 'Patient_001'")
    age_range = models.CharField(max_length=20, help_text="e.g. '30-40'")
    gender = models.CharField(max_length=1)
    diagnosis = models.CharField(max_length=255)
    medication = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.anonymized_label} ({self.dataset_id})"

