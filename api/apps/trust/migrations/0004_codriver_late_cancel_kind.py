from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trust", "0003_seatwanted_flex_days_and_more"),
        ("bookings", "0003_codriver_role"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reliabilityevent",
            name="kind",
            field=models.CharField(max_length=24, choices=[
                ("trip_completed", "Trip completed"),
                ("passenger_early_cancel", "Passenger cancelled early"),
                ("passenger_late_cancel", "Passenger cancelled late"),
                ("codriver_late_cancel", "Co-driver cancelled late"),
                ("driver_early_cancel", "Driver cancelled early"),
                ("driver_late_cancel", "Driver cancelled late"),
                ("driver_change", "Driver moved departure"),
                ("no_show", "No-show"),
                ("refund_overdue", "Refund overdue"),
                ("refund_resolved", "Overdue refund confirmed"),
                ("correction", "Correction"),
            ]),
        ),
    ]
