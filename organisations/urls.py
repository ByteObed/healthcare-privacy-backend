
from django.urls import path
from .views import (
    RegisterOrganisationView,
    OrganisationListView,
    OrganisationDetailView,
    CurrentOrganisationView,
    PublicKeyView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    # Anonymization views from organisations/views.py
    ReceivedAnonymizedDatasetsView,
    SentAnonymizedDatasetsView,
    ExportAnonymizedDatasetView,
)

urlpatterns = [
    # Organisation endpoints
    path('register/', RegisterOrganisationView.as_view(), name='register-organisation'),
    path('me/', CurrentOrganisationView.as_view(), name='current-organisation'),
    path('public-key/', PublicKeyView.as_view(), name='public-key'),
    path('', OrganisationListView.as_view(), name='organisation-list'),
    path('<int:pk>/', OrganisationDetailView.as_view(), name='organisation-detail'),
    
    # Password reset endpoints
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    
    # Anonymization endpoints
    path('anonymization/received/', ReceivedAnonymizedDatasetsView.as_view(), name='anonymization-received'),
    path('anonymization/sent/', SentAnonymizedDatasetsView.as_view(), name='anonymization-sent'),
    path('anonymization/export/', ExportAnonymizedDatasetView.as_view(), name='anonymization-export'),
]