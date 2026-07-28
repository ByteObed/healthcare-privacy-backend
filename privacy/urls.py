
from django.urls import path
from .views import (
    PrivacyResultListView,
    PrivacyComparisonView,
    SendEncryptedRecordView,
    SentEncryptedRecordsListView,
    SentAnonymizedDatasetsListView,
    ReceivedEncryptedRecordsListView,
    RetrieveEncryptionKeyView,
    DecryptRecordView,
    RegenerateEncryptionKeyView,
    ExportAnonymizedDatasetView,
    ReceivedAnonymizedDatasetsListView,
    MaskedPatientListView,
    ApplyMaskingLogView,
    DifferentialPrivacyQueryView,
)

urlpatterns = [
    path('', PrivacyResultListView.as_view(), name='privacy-result-list'),
    path('comparison/', PrivacyComparisonView.as_view(), name='privacy-comparison'),

    # Encryption
    path('encryption/send/', SendEncryptedRecordView.as_view(), name='send-encrypted-record'),
    path('encryption/sent/', SentEncryptedRecordsListView.as_view(), name='encryption-sent'),
    path('encryption/received/', ReceivedEncryptedRecordsListView.as_view(), name='received-encrypted-records'),
    path('encryption/<int:pk>/key/', RetrieveEncryptionKeyView.as_view(), name='retrieve-encryption-key'),
    path('encryption/<int:pk>/decrypt/', DecryptRecordView.as_view(), name='decrypt-record'),
    path('encryption/<int:pk>/regenerate-key/', RegenerateEncryptionKeyView.as_view(), name='encryption-regenerate-key'),

    # Anonymization
    path('anonymization/export/', ExportAnonymizedDatasetView.as_view(), name='export-anonymized-dataset'),
    path('anonymization/received/', ReceivedAnonymizedDatasetsListView.as_view(), name='received-anonymized-datasets'),
    path('anonymization/sent/', SentAnonymizedDatasetsListView.as_view(), name='anonymization-sent'),

    # Masking
    path('masking/view/', MaskedPatientListView.as_view(), name='masked-patient-list'),
    path('masking/apply/', ApplyMaskingLogView.as_view(), name='apply-masking-log'),

    # Differential Privacy
    path('differential-privacy/query/', DifferentialPrivacyQueryView.as_view(), name='differential-privacy-query'),
]