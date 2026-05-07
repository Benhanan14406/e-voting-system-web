import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user= models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    integrity_hash = models.CharField(max_length=64)
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-logged_at"]
        
    def delete(self, *args, **kwargs):
        raise PermissionDenied("Audit log entries cannot be deleted.")
 
    class ImmutableQuerySet(models.QuerySet):
        def delete(self):
            raise PermissionDenied("Audit log entries cannot be deleted.")
 
    objects = ImmutableQuerySet.as_manager()