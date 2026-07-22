from django.urls import path
from .views import (
    RegisterOrganisationView,
    OrganisationListView,
    OrganisationDetailView,
    CurrentOrganisationView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
)

urlpatterns = [
    path('register/', RegisterOrganisationView.as_view(), name='register-organisation'),
    path('me/', CurrentOrganisationView.as_view(), name='current-organisation'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('', OrganisationListView.as_view(), name='organisation-list'),
    path('<int:pk>/', OrganisationDetailView.as_view(), name='organisation-detail'),
]