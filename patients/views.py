
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from organisations.permissions import IsOrganisationUser
from .models import Patient
from .serializers import PatientSerializer, PatientCreateSerializer
import pandas as pd
from rest_framework.parsers import MultiPartParser


class PatientListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]
    filterset_fields = ['gender', 'diagnosis']
    search_fields = ['name', 'patient_id', 'diagnosis']
    ordering_fields = ['age', 'created_at']
    pagination_class = None 

    def get_queryset(self):
        return Patient.objects.filter(organisation=self.request.user.organisation)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PatientCreateSerializer
        return PatientSerializer


class PatientDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]

    def get_queryset(self):
        return Patient.objects.filter(organisation=self.request.user.organisation)



class ImportPatientsExcelView(APIView):
    """Hospital A (or any org) uploads an Excel file to bulk-import patients."""
    permission_classes = [permissions.IsAuthenticated, IsOrganisationUser]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file uploaded. Use form field 'file'."}, status=400)

        try:
            df = pd.read_excel(file_obj)
        except Exception as e:
            return Response({"error": f"Could not read Excel file: {str(e)}"}, status=400)

        required_columns = {'patient_id', 'name', 'age', 'gender', 'phone_number', 'diagnosis', 'medication'}
        if not required_columns.issubset(set(df.columns)):
            missing = required_columns - set(df.columns)
            return Response({"error": f"Missing required columns: {list(missing)}"}, status=400)

        organisation = request.user.organisation
        created_count = 0
        skipped_rows = []

        for _, row in df.iterrows():
            try:
                Patient.objects.update_or_create(
                    organisation=organisation,
                    patient_id=str(row['patient_id']),
                    defaults={
                        'name': str(row['name']),
                        'age': int(row['age']),
                        'gender': str(row['gender']).strip().upper()[0],
                        'phone_number': str(row['phone_number']),
                        'diagnosis': str(row['diagnosis']),
                        'medication': str(row['medication']),
                    }
                )
                created_count += 1
            except Exception as e:
                skipped_rows.append({"row": row.to_dict(), "error": str(e)})

        return Response({
            "message": f"{created_count} patients imported successfully.",
            "skipped": skipped_rows,
        }, status=status.HTTP_201_CREATED)


