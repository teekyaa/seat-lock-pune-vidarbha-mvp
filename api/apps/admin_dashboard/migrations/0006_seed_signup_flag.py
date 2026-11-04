from django.db import migrations


def seed_flag(apps, schema_editor):
    flag = apps.get_model("admin_dashboard", "FeatureFlag")
    flag.objects.get_or_create(key="signup.new_signups_enabled", defaults={"value": True})


class Migration(migrations.Migration):
    dependencies = [("admin_dashboard", "0005_seed_supported_flags")]
    operations = [migrations.RunPython(seed_flag, migrations.RunPython.noop)]
