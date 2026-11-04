from rest_framework.permissions import BasePermission

from .audit import record_event
from .permissions import has_permission


class RequiresAdminPermission(BasePermission):
    """Every protected admin view declares required_permission; missing means deny."""

    def has_permission(self, request, view):
        admin = request.user
        if not admin or not admin.is_authenticated:
            return False
        required = getattr(view, "required_permission", None)
        if not required or not has_permission(admin.role, required):
            record_event(request, "permission_denied", admin=admin, resource_type="admin_endpoint")
            return False
        return True
