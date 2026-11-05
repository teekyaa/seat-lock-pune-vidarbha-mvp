from django.db import migrations


def seed_flags(apps, schema_editor):
    flag = apps.get_model("admin_dashboard", "FeatureFlag")
    for key in ("rides.new_ride_creation_enabled", "bookings.new_bookings_enabled"):
        flag.objects.get_or_create(key=key, defaults={"value": True})


class Migration(migrations.Migration):
    dependencies = [("admin_dashboard", "0004_featureflag_featureflagchange")]
    operations = [migrations.RunPython(seed_flags, migrations.RunPython.noop)]
