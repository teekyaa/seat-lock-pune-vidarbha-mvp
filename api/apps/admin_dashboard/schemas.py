from rest_framework import serializers


class AdminLoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=1024, write_only=True, trim_whitespace=False)
    code = serializers.CharField(max_length=6, write_only=True)


class AdminLoginIdentitySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    role = serializers.CharField()


class AdminLoginResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    admin = AdminLoginIdentitySerializer()


class AdminReauthenticationSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=1024, write_only=True, trim_whitespace=False)
    code = serializers.CharField(max_length=6, write_only=True)


class FeatureFlagSerializer(serializers.Serializer):
    key = serializers.CharField()
    description = serializers.CharField()
    value = serializers.BooleanField()
    default = serializers.BooleanField()
    is_critical = serializers.BooleanField()
    updated_at = serializers.DateTimeField(allow_null=True)
    updated_by = serializers.CharField(allow_null=True)


class FeatureFlagUpdateSerializer(serializers.Serializer):
    value = serializers.BooleanField()
    reason = serializers.CharField(max_length=1000)
    confirmation = serializers.CharField(max_length=120)


class FeatureFlagChangeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    old_value = serializers.BooleanField()
    new_value = serializers.BooleanField()
    changed_by = serializers.CharField()
    reason = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


class PlatformSettingSerializer(serializers.Serializer):
    key = serializers.CharField()
    value = serializers.IntegerField(allow_null=True)
    description = serializers.CharField()
    minimum = serializers.IntegerField()
    maximum = serializers.IntegerField()
    updated_at = serializers.DateTimeField(allow_null=True)


class PlatformSettingUpdateSerializer(serializers.Serializer):
    value = serializers.IntegerField(allow_null=True)
    reason = serializers.CharField(max_length=1000)


class AdminAuditEntrySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    admin_id = serializers.UUIDField(allow_null=True)
    admin_name = serializers.CharField(allow_null=True)
    admin_role = serializers.CharField(allow_blank=True)
    action = serializers.CharField()
    resource_type = serializers.CharField(allow_blank=True)
    resource_id = serializers.CharField(allow_blank=True)
    before = serializers.JSONField()
    after = serializers.JSONField()
    reason = serializers.CharField(allow_blank=True)
    request_id = serializers.UUIDField()
    ip_address = serializers.IPAddressField(allow_null=True)
    user_agent = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class AdminAuditPageSerializer(serializers.Serializer):
    results = AdminAuditEntrySerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class AdminIdentitySerializer(AdminLoginIdentitySerializer):
    permissions = serializers.ListField(child=serializers.CharField())


class AdminOverviewSerializer(serializers.Serializer):
    as_of = serializers.DateTimeField()
    rides_scheduled_today = serializers.IntegerField(min_value=0)
    rides_next_24_hours = serializers.IntegerField(min_value=0)
    held_seats = serializers.IntegerField(min_value=0)
    open_reports = serializers.IntegerField(min_value=0)
    new_signups_today = serializers.IntegerField(min_value=0)


class AdminErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    request_id = serializers.UUIDField()
    details = serializers.JSONField()


class AdminErrorSerializer(serializers.Serializer):
    error = AdminErrorDetailSerializer()
