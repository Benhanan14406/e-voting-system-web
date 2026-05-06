import pyotp
import qrcode
import io
import base64


def generate_totp_secret() -> str:
    return pyotp.random_base32()

def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)

def get_totp_uri(secret: str, username: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name="E-Voting System")

def generate_qr_code_base64(secret: str, username: str) -> str:
    uri = get_totp_uri(secret, username)
    img = qrcode.make(uri)
    buffer = io.BytesIO()
    img.save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return encoded