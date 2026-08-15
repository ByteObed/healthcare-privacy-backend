from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Organisation
from .utils import generate_rsa_keypair


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class OrganisationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    patient_count = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = ['id', 'user', 'name', 'organisation_type', 'location', 'public_key', 'created_at', 'patient_count']

    def get_patient_count(self, obj):
        return obj.patients.count()


# class RegisterOrganisationSerializer(serializers.ModelSerializer):
#     username = serializers.CharField(write_only=True)
#     password = serializers.CharField(write_only=True)
#     email = serializers.EmailField(write_only=True)

#     class Meta:
#         model = Organisation
#         fields = ['username', 'password', 'email', 'name', 'organisation_type', 'location']

#     def create(self, validated_data):
#         username = validated_data.pop('username')
#         password = validated_data.pop('password')
#         email = validated_data.pop('email')

#         user = User.objects.create_user(username=username, password=password, email=email)
#         organisation = Organisation.objects.create(user=user, **validated_data)
#         return organisation



class RegisterOrganisationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)

    class Meta:
        model = Organisation
        fields = ['username', 'password', 'email', 'name', 'organisation_type', 'location']

    def create(self, validated_data):
        username = validated_data.pop('username')
        password = validated_data.pop('password')
        email = validated_data.pop('email')

        user = User.objects.create_user(username=username, password=password, email=email)

        private_pem, public_pem = generate_rsa_keypair()

        organisation = Organisation.objects.create(
            user=user,
            public_key=public_pem,
            private_key=private_pem,
            **validated_data
        )
        return organisation

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)        