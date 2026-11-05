from django.db import migrations


def protect_events(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION admin_audit_reject_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'admin audit events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    schema_editor.execute("""
        CREATE TRIGGER admin_audit_no_update_delete
        BEFORE UPDATE OR DELETE ON admin_dashboard_adminauditevent
        FOR EACH ROW EXECUTE FUNCTION admin_audit_reject_mutation()
    """)


def unprotect_events(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP TRIGGER IF EXISTS admin_audit_no_update_delete ON admin_dashboard_adminauditevent")
    schema_editor.execute("DROP FUNCTION IF EXISTS admin_audit_reject_mutation()")


class Migration(migrations.Migration):
    dependencies = [("admin_dashboard", "0001_initial")]
    operations = [migrations.RunPython(protect_events, unprotect_events)]
