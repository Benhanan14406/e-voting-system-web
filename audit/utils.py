import hashlib
from django.utils import timezone
from .models import AuditLog

def log_action(request, action, details=''):
    user = request.user if request.user.is_authenticated else None
    ip = _get_client_ip(request)
    timestamp = timezone.now().isoformat()

    raw = f"{user}|{action}|{details}|{ip}|{timestamp}"
    integrity_hash = hashlib.sha256(raw.encode()).hexdigest()

    AuditLog.objects.create(
        user=user,
        action=action,
        details=details,
        ip_address=ip,
        integrity_hash=integrity_hash,
    )

def _get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")