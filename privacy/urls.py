
from django.urls import path
from .views import (
    PrivacyResultListView,
    PrivacyComparisonView,
    SendEncryptedRecordView,
    SentAnonymizedDatasetsListView,
    ReceivedEncryptedRecordsListView,
    RetrieveEncryptionKeyView,
    DecryptRecordView,
    ExportAnonymizedDatasetView,
    ReceivedAnonymizedDatasetsListView,
    MaskedPatientListView,
    DifferentialPrivacyQueryView,
)

urlpatterns = [
    path('', PrivacyResultListView.as_view(), name='privacy-result-list'),
    path('comparison/', PrivacyComparisonView.as_view(), name='privacy-comparison'),

    # Encryption
    path('encryption/send/', SendEncryptedRecordView.as_view(), name='send-encrypted-record'),
    path('encryption/received/', ReceivedEncryptedRecordsListView.as_view(), name='received-encrypted-records'),
    path('encryption/<int:pk>/key/', RetrieveEncryptionKeyView.as_view(), name='retrieve-encryption-key'),
    path('encryption/<int:pk>/decrypt/', DecryptRecordView.as_view(), name='decrypt-record'),

    # Anonymization
    path('anonymization/export/', ExportAnonymizedDatasetView.as_view(), name='export-anonymized-dataset'),
    path('anonymization/received/', ReceivedAnonymizedDatasetsListView.as_view(), name='received-anonymized-datasets'),
    path('anonymization/sent/', SentAnonymizedDatasetsListView.as_view(), name='anonymization-sent'),

    # Masking
    path('masking/view/', MaskedPatientListView.as_view(), name='masked-patient-list'),

    # Differential Privacy
    path('differential-privacy/query/', DifferentialPrivacyQueryView.as_view(), name='differential-privacy-query'),
]