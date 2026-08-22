# organisations/models.py
from django.db import models
from django.contrib.auth.models import User

class Organisation(models.Model):
    ORGANISATION_TYPES = [
        ('hospital', 'Hospital'),
        ('clinic', 'Clinic'),
        ('research', 'Research Center'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organisation')
    name = models.CharField(max_length=255)
    organisation_type = models.CharField(max_length=50, choices=ORGANISATION_TYPES)
    location = models.CharField(max_length=255)
    public_key = models.TextField(blank=True, null=True, help_text="RSA public key, safe to share with other organisations")
    private_key = models.TextField(blank=True, null=True, help_text="RSA private key, NEVER leaves this server's own database")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

