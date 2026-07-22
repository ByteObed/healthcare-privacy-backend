import time
import json
import pandas as pd
from cryptography.fernet import Fernet
from diffprivlib.mechanisms import Laplace


def generate_fernet_key():
    """Generate a new Fernet key for one encryption operation."""
    return Fernet.generate_key().decode()


def encrypt_patient_record(patient_data: dict, key: str) -> str:
    """Encrypt a patient record dict into a Fernet ciphertext string."""
    fernet = Fernet(key.encode())
    json_bytes = json.dumps(patient_data).encode()
    encrypted_bytes = fernet.encrypt(json_bytes)
    return encrypted_bytes.decode()


def decrypt_patient_record(encrypted_payload: str, key: str) -> dict:
    """Decrypt a Fernet ciphertext string back into a patient record dict."""
    fernet = Fernet(key.encode())
    decrypted_bytes = fernet.decrypt(encrypted_payload.encode())
    return json.loads(decrypted_bytes.decode())


def anonymize_patient_records(patients):
    """Convert a queryset of Patient objects into anonymized records using Pandas."""
    data = [{
        "patient_id": p.patient_id,
        "age": p.age,
        "gender": p.gender,
        "diagnosis": p.diagnosis,
        "medication": p.medication,
    } for p in patients]

    df = pd.DataFrame(data)

    if df.empty:
        return []

    def age_to_range(age):
        lower = (age // 10) * 10
        upper = lower + 10
        return f"{lower}-{upper}"

    df['age_range'] = df['age'].apply(age_to_range)
    df['anonymized_label'] = ['Patient_' + str(i + 1).zfill(3) for i in range(len(df))]

    anonymized = df[['anonymized_label', 'age_range', 'gender', 'diagnosis', 'medication']]
    return anonymized.to_dict(orient='records')


def mask_name(name: str) -> str:
    """Show first name fully, mask last name. E.g. 'Kwame Asante' -> 'Kwame A****'"""
    parts = name.strip().split(' ', 1)
    if len(parts) == 1:
        return parts[0][0] + '*' * (len(parts[0]) - 1)
    first, last = parts
    masked_last = last[0] + '*' * (len(last) - 1) if len(last) > 1 else last
    return f"{first} {masked_last}"


def mask_patient_id(patient_id: str) -> str:
    """Show first 1 and last 1 characters, mask the middle. E.g. 'P001' -> 'P**1'"""
    if len(patient_id) <= 2:
        return patient_id
    return patient_id[0] + '*' * (len(patient_id) - 2) + patient_id[-1]


def mask_phone_number(phone: str) -> str:
    """Show first 4 and last 3 digits, mask the middle. E.g. '0244123456' -> '0244***456'"""
    if len(phone) <= 7:
        return '*' * len(phone)
    return phone[:4] + '*' * (len(phone) - 7) + phone[-3:]


## diffprivlib

def apply_differential_privacy_count(true_count: int, epsilon: float = 1.0) -> int:
    """Add Laplace noise to a count using diffprivlib, simulating differential privacy."""
    mechanism = Laplace(epsilon=epsilon, sensitivity=1)
    noisy_value = mechanism.randomise(true_count)
    return max(0, round(noisy_value))  # counts can't be negative


def apply_differential_privacy_mean(true_mean: float, epsilon: float = 1.0, sensitivity: float = 5.0) -> float:
    """Add Laplace noise to a mean (e.g. average age) using diffprivlib."""
    mechanism = Laplace(epsilon=epsilon, sensitivity=sensitivity)
    noisy_value = mechanism.randomise(true_mean)
    return round(noisy_value, 1)