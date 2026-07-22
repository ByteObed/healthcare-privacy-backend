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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name