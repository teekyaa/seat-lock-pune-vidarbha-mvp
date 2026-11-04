"""Central role-to-permission mapping for the separate admin security boundary.

Permissions describe authorized capabilities, not whether an endpoint exists.
Unrecognized roles or permissions never grant access.
"""
from enum import StrEnum


class AdminRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    OPS_ADMIN = "OPS_ADMIN"
    SUPPORT_AGENT = "SUPPORT_AGENT"
    FINANCE_ADMIN = "FINANCE_ADMIN"
    TRUST_SAFETY = "TRUST_SAFETY"
    VIEWER = "VIEWER"


class Permission(StrEnum):
    SESSION_READ = "session:read"
    SESSION_LOGOUT = "session:logout"
    SESSION_REAUTHENTICATE = "session:reauthenticate"
    OVERVIEW_READ = "overview:read"
    USERS_READ = "users:read"
    USERS_REVEAL_PII = "users:reveal_pii"
    USERS_WARN = "users:warn"
    USERS_NOTES = "users:notes"
    USERS_SUSPEND = "users:suspend"
    USERS_BAN = "users:ban"
    USERS_VERIFY = "users:verify"
    RIDES_READ = "rides:read"
    RIDES_CANCEL = "rides:cancel"
    SEAT_LOCKS_READ = "seat_locks:read"
    SEAT_LOCKS_RELEASE = "seat_locks:release"
    SEAT_LOCKS_EXTEND = "seat_locks:extend"
    PAYMENTS_READ = "payments:read"
    REFUNDS_CREATE = "refunds:create"
    PAYOUTS_HOLD = "payouts:hold"
    RECONCILIATION_RUN = "reconciliation:run"
    TICKETS_READ = "tickets:read"
    TICKETS_ASSIGN = "tickets:assign"
    TICKETS_RESOLVE = "tickets:resolve"
    TICKETS_ESCALATE = "tickets:escalate"
    TICKETS_REPLY = "tickets:reply"
    TICKETS_NOTE = "tickets:note"
    FLAGS_READ = "flags:read"
    FLAGS_REVIEW = "flags:review"
    RISK_RULES_MANAGE = "risk_rules:manage"
    FEATURE_FLAGS_READ = "feature_flags:read"
    FEATURE_FLAGS_TOGGLE = "feature_flags:toggle"
    FEATURE_FLAGS_TOGGLE_CRITICAL = "feature_flags:toggle_critical"
    AUDIT_LOGS_READ = "audit_logs:read"
    SYSTEM_LOGS_READ = "system_logs:read"
    ADMINS_MANAGE = "admins:manage"
    SETTINGS_MANAGE = "settings:manage"
    EXPORTS_CREATE = "exports:create"
    ALERTS_ACKNOWLEDGE = "alerts:acknowledge"


SESSION_PERMISSIONS = frozenset({Permission.SESSION_READ, Permission.SESSION_LOGOUT, Permission.SESSION_REAUTHENTICATE})
READ_ONLY = SESSION_PERMISSIONS | frozenset({
    Permission.OVERVIEW_READ, Permission.USERS_READ, Permission.RIDES_READ,
    Permission.SEAT_LOCKS_READ, Permission.PAYMENTS_READ, Permission.TICKETS_READ,
    Permission.FLAGS_READ, Permission.FEATURE_FLAGS_READ,
})
ROLE_PERMISSIONS = {
    AdminRole.SUPER_ADMIN: frozenset(Permission),
    AdminRole.VIEWER: READ_ONLY,
    AdminRole.OPS_ADMIN: READ_ONLY | frozenset({
        Permission.USERS_VERIFY, Permission.RIDES_CANCEL, Permission.SEAT_LOCKS_RELEASE,
        Permission.SEAT_LOCKS_EXTEND, Permission.TICKETS_ASSIGN, Permission.TICKETS_RESOLVE,
        Permission.TICKETS_ESCALATE, Permission.TICKETS_REPLY, Permission.TICKETS_NOTE,
        Permission.ALERTS_ACKNOWLEDGE, Permission.FEATURE_FLAGS_TOGGLE,
    }),
    AdminRole.SUPPORT_AGENT: SESSION_PERMISSIONS | frozenset({
        Permission.OVERVIEW_READ, Permission.USERS_READ, Permission.USERS_WARN, Permission.USERS_NOTES,
        Permission.RIDES_READ, Permission.SEAT_LOCKS_READ, Permission.TICKETS_READ,
        Permission.TICKETS_ASSIGN, Permission.TICKETS_RESOLVE, Permission.TICKETS_ESCALATE,
        Permission.TICKETS_REPLY, Permission.TICKETS_NOTE, Permission.FEATURE_FLAGS_READ,
    }),
    AdminRole.FINANCE_ADMIN: SESSION_PERMISSIONS | frozenset({
        Permission.OVERVIEW_READ, Permission.PAYMENTS_READ, Permission.REFUNDS_CREATE,
        Permission.PAYOUTS_HOLD, Permission.RECONCILIATION_RUN, Permission.FEATURE_FLAGS_READ,
    }),
    AdminRole.TRUST_SAFETY: SESSION_PERMISSIONS | frozenset({
        Permission.OVERVIEW_READ, Permission.USERS_READ, Permission.USERS_WARN, Permission.USERS_NOTES,
        Permission.USERS_SUSPEND, Permission.USERS_BAN, Permission.FLAGS_READ,
        Permission.FLAGS_REVIEW, Permission.RISK_RULES_MANAGE, Permission.TICKETS_READ,
        Permission.TICKETS_ASSIGN, Permission.TICKETS_ESCALATE, Permission.FEATURE_FLAGS_READ,
    }),
}


def has_permission(role: str, permission: str) -> bool:
    try:
        return Permission(permission) in ROLE_PERMISSIONS[AdminRole(role)]
    except (ValueError, KeyError, TypeError):
        return False


def render_permission_matrix() -> str:
    roles = list(AdminRole)
    lines = [
        "# Admin permission matrix",
        "",
        "Generated from `api/apps/admin_dashboard/permissions.py`. A permission does not imply the feature is implemented.",
        "",
        "| Permission | " + " | ".join(role.value for role in roles) + " |",
        "| --- | " + " | ".join("---" for _ in roles) + " |",
    ]
    for permission in Permission:
        cells = ["yes" if permission in ROLE_PERMISSIONS[role] else "—" for role in roles]
        lines.append(f"| `{permission.value}` | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
