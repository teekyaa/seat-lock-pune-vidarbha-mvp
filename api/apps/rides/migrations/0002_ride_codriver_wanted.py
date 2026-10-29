from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rides", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="ride",
            name="codriver_wanted",
            field=models.BooleanField(default=False),
        ),
    ]
