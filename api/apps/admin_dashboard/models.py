import uuid

from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils import timezone

from .permissions import AdminRole


class AdminAccount(models.Model):
    """An operator identity that is independent of the rider/driver User model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=20, choices=[(role.value, role.value) for role in AdminRole])
    password_hash = models.CharField(max_length=256)
    totp_secret_encrypted = models.TextField()
    last_totp_counter = models.BigIntegerField(default=-1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="admin_email_case_insensitive_unique"),
            models.CheckConstraint(condition=models.Q(role__in=[role.value for role in AdminRole]),
                                   name="admin_role_valid"),
        ]

    @property
    def is_authenticated(self):
        return True

    def save(self, *args, **kwargs):
        if not self._state.adding and not self.is_active:
            with transaction.atomic():
                result = super().save(*args, **kwargs)
                AdminSession.objects.filter(admin_id=self.pk, revoked_at__isnull=True).update(revoked_at=timezone.now())
                return result
        return super().save(*args, **kwargs)


class AdminSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(AdminAccount, on_delete=models.CASCADE, related_name="sessions")
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField()
    reauthenticated_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)


class AdminAuditEvent(models.Model):
    """Admin security and mutation history; database protection is a release gate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(AdminAccount, null=True, blank=True, on_delete=models.PROTECT)
    admin_role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=80, db_index=True)
    resource_type = models.CharField(max_length=80, blank=True)
    resource_id = models.CharField(max_length=120, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    reason = models.CharField(max_length=1000, blank=True)
    request_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "-id"], name="admin_audit_cursor_idx"),
            models.Index(fields=["resource_type", "resource_id", "-created_at"], name="admin_audit_resource_idx"),
            models.Index(fields=["admin", "-created_at"], name="admin_audit_actor_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Admin audit events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Admin audit events are append-only.")


class FeatureFlag(models.Model):
    key = models.CharField(max_length=120, primary_key=True)
    value = models.BooleanField()
    updated_by = models.ForeignKey(AdminAccount, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FeatureFlagChange(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flag = models.ForeignKey(FeatureFlag, on_delete=models.PROTECT, related_name="changes")
    changed_by = models.ForeignKey(AdminAccount, on_delete=models.PROTECT)
    old_value = models.BooleanField()
    new_value = models.BooleanField()
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class PlatformSetting(models.Model):
    key = models.CharField(max_length=120, primary_key=True)
    value = models.PositiveIntegerField(null=True, blank=True)
    updated_by = models.ForeignKey(AdminAccount, null=True, blank=True, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)
