from rest_framework import serializers
from .models import Patient


class PatientSerializer(serializers.ModelSerializer):
    organisation_name = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            'id', 'patient_id', 'name', 'age', 'gender', 'phone_number',
            'diagnosis', 'medication', 'organisation_name', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_organisation_name(self, obj):
        return obj.organisation.name


class PatientCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['patient_id', 'name', 'age', 'gender', 'phone_number', 'diagnosis', 'medication']

    def create(self, validated_data):
        organisation = self.context['request'].user.organisation
        return Patient.objects.create(organisation=organisation, **validated_data)


