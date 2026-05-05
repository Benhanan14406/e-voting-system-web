from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.shortcuts import render
from .models import AuditLog

class AuditLogView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role == "Admin"

    def get(self, request):
        logs = AuditLog.objects.select_related('user').all()[:200]
        return render(request, "udit/log.html", {"logs": logs})