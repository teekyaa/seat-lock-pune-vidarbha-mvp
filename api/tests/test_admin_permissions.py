from pathlib import Path

from apps.admin_dashboard.permissions import AdminRole, Permission, ROLE_PERMISSIONS, has_permission, render_permission_matrix


def test_all_roles_have_explicit_permission_sets():
    assert set(ROLE_PERMISSIONS) == set(AdminRole)
    assert all(isinstance(permissions, frozenset) for permissions in ROLE_PERMISSIONS.values())


def test_only_super_admin_has_critical_controls_and_pii_reveal():
    for role in AdminRole:
        expected = role == AdminRole.SUPER_ADMIN
        assert has_permission(role, Permission.FEATURE_FLAGS_TOGGLE_CRITICAL) is expected
        assert has_permission(role, Permission.USERS_REVEAL_PII) is expected
        assert has_permission(role, Permission.ADMINS_MANAGE) is expected


def test_viewer_has_no_mutation_permissions():
    assert all(permission.value.endswith(':read') or permission in {Permission.SESSION_LOGOUT, Permission.SESSION_REAUTHENTICATE}
               for permission in ROLE_PERMISSIONS[AdminRole.VIEWER])


def test_invalid_or_unrecognized_values_fail_closed():
    assert not has_permission('RIDER', Permission.OVERVIEW_READ)
    assert not has_permission(AdminRole.SUPER_ADMIN, 'undefined:action')
    assert not has_permission(None, None)


def test_roles_have_distinct_authority():
    assert has_permission(AdminRole.FINANCE_ADMIN, Permission.REFUNDS_CREATE)
    assert not has_permission(AdminRole.SUPPORT_AGENT, Permission.REFUNDS_CREATE)
    assert has_permission(AdminRole.TRUST_SAFETY, Permission.USERS_SUSPEND)
    assert not has_permission(AdminRole.OPS_ADMIN, Permission.USERS_SUSPEND)


def test_documented_matrix_matches_permission_source():
    document = Path(__file__).resolve().parents[2] / 'docs' / 'admin' / 'RBAC.md'
    assert document.read_text(encoding='utf-8') == render_permission_matrix()
