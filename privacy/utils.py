# keep your old Fernet-only functions too
import time
import json
import pandas as pd
from cryptography.fernet import Fernet
from diffprivlib.mechanisms import Laplace


# def generate_fernet_key():
#     """Generate a new Fernet key for one encryption operation."""
#     return Fernet.generate_key().decode()


# def encrypt_patient_record(patient_data: dict, key: str) -> str:
#     """Encrypt a patient record dict into a Fernet ciphertext string."""
#     fernet = Fernet(key.encode())
#     json_bytes = json.dumps(patient_data).encode()
#     encrypted_bytes = fernet.encrypt(json_bytes)
#     return encrypted_bytes.decode()


# def decrypt_patient_record(encrypted_payload: str, key: str) -> dict:
#     """Decrypt a Fernet ciphertext string back into a patient record dict."""
#     fernet = Fernet(key.encode())
#     decrypted_bytes = fernet.decrypt(encrypted_payload.encode())
#     return json.loads(decrypted_bytes.decode())


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


    # New Fernet
    import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
import base64


def generate_session_key():
    """Generate a one-time symmetric key for a single transfer."""
    return Fernet.generate_key()


def encrypt_data_with_session_key(data: dict, session_key: bytes) -> str:
    """Encrypt the actual patient data using the fast symmetric session key."""
    fernet = Fernet(session_key)
    json_bytes = json.dumps(data).encode()
    return fernet.encrypt(json_bytes).decode()


def decrypt_data_with_session_key(encrypted_data: str, session_key: bytes) -> dict:
    """Decrypt patient data using the recovered symmetric session key."""
    fernet = Fernet(session_key)
    decrypted_bytes = fernet.decrypt(encrypted_data.encode())
    return json.loads(decrypted_bytes.decode())


def encrypt_session_key_with_public_key(session_key: bytes, public_key_pem: str) -> str:
    """Encrypt the session key using the RECEIVER's RSA public key."""
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    encrypted = public_key.encrypt(
        session_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        )
    )
    return base64.b64encode(encrypted).decode()


def decrypt_session_key_with_private_key(encrypted_session_key: str, private_key_pem: str) -> bytes:
    """Decrypt the session key using the RECEIVER's OWN RSA private key."""
    private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    encrypted_bytes = base64.b64decode(encrypted_session_key)
    session_key = private_key.decrypt(
        encrypted_bytes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        )
    )
    return session_key


def sign_data(data: dict, private_key_pem: str) -> str:
    """SENDER signs a SHA-256 hash of the plaintext using their OWN private key — proves authenticity + integrity."""
    private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    json_bytes = json.dumps(data, sort_keys=True).encode()
    signature = private_key.sign(
        json_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


def verify_signature(data: dict, signature_b64: str, public_key_pem: str) -> bool:
    """RECEIVER verifies the signature using the SENDER's public key."""
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    json_bytes = json.dumps(data, sort_keys=True).encode()
    signature = base64.b64decode(signature_b64)
    try:
        public_key.verify(
            signature,
            json_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False