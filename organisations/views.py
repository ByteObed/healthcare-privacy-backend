from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Organisation
from .serializers import OrganisationSerializer, RegisterOrganisationSerializer

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User

from .serializers import PasswordResetRequestSerializer, PasswordResetConfirmSerializer

token_generator = PasswordResetTokenGenerator()


class PasswordResetRequestView(APIView):
    """User submits their email, receives a reset link if the account exists."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal whether the email exists — always return success
            return Response(
                {"message": "If an account with that email exists, a reset link has been sent."},
                status=200
            )

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        send_mail(
            subject="Reset your Healthcare Privacy System password",
            message=f"Hi {user.username},\n\nClick the link below to reset your password:\n{reset_link}\n\nIf you didn't request this, ignore this email.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(
            {"message": "If an account with that email exists, a reset link has been sent."},
            status=200
        )


class PasswordResetConfirmView(APIView):
    """User submits uid, token, and new password to complete the reset."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({"error": "Invalid reset link."}, status=400)

        if not token_generator.check_token(user, token):
            return Response({"error": "Invalid or expired reset link."}, status=400)

        user.set_password(new_password)
        user.save()

        return Response({"message": "Password has been reset successfully."}, status=200)


class RegisterOrganisationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterOrganisationSerializer(data=request.data)
        if serializer.is_valid():
            organisation = serializer.save()
            return Response(
                OrganisationSerializer(organisation).data,
                status=201
            )
        return Response(serializer.errors, status=400)


class OrganisationListView(generics.ListAPIView):
    queryset = Organisation.objects.all()
    serializer_class = OrganisationSerializer
    permission_classes = [permissions.IsAuthenticated]


class OrganisationDetailView(generics.RetrieveAPIView):
    queryset = Organisation.objects.all()
    serializer_class = OrganisationSerializer
    permission_classes = [permissions.IsAuthenticated]


class CurrentOrganisationView(APIView):
    """Returns the logged-in user's own organisation details."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'organisation'):
            return Response({"error": "This user has no linked organisation."}, status=403)
        return Response(OrganisationSerializer(request.user.organisation).data)    

class PublicKeyView(APIView):
    """Public endpoint — returns this server's organisation's RSA public key. No auth required, since public keys are meant to be shared openly."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        organisation = Organisation.objects.first()
        if not organisation or not organisation.public_key:
            return Response({"error": "No organisation with a public key registered on this server."}, status=404)

        return Response({
            "organisation_name": organisation.name,
            "organisation_id": organisation.id,
            "public_key": organisation.public_key,
        })        