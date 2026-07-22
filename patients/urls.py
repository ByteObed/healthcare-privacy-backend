from django.urls import path
from .views import PatientListCreateView, PatientDetailView, ImportPatientsExcelView

urlpatterns = [
    path('', PatientListCreateView.as_view(), name='patient-list-create'),
    path('<int:pk>/', PatientDetailView.as_view(), name='patient-detail'),
    path('import-excel/', ImportPatientsExcelView.as_view(), name='import-patients-excel'),
   
]