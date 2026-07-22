from django.db import models
from organisations.models import Organisation


class Patient(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='patients')
    patient_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone_number = models.CharField(max_length=20, blank=True, default="0000000000")
    diagnosis = models.CharField(max_length=255)
    medication = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organisation', 'patient_id')
        ordering = ['patient_id']

    def __str__(self):
        return f"{self.patient_id} - {self.name}"