import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Doctor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("department", models.CharField(choices=[("CARDIOLOGY", "Cardiology"), ("PEDIATRICS", "Pediatrics"), ("ORTHOPEDICS", "Orthopedics"), ("NEUROLOGY", "Neurology")], max_length=20)),
                ("specialization", models.CharField(max_length=120)),
                ("consultation_fee", models.DecimalField(decimal_places=2, max_digits=8, validators=[django.core.validators.MinValueValidator(0)])),
                ("available_days", models.CharField(default="MON,TUE,WED,THU,FRI", max_length=40)),
                ("experience_years", models.PositiveSmallIntegerField(default=5)),
                ("bio", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["department", "name"],
            },
        ),
        migrations.CreateModel(
            name="Patient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=120)),
                ("phone", models.CharField(max_length=15, validators=[django.core.validators.RegexValidator("^\\+?\\d{10,14}$", "Enter a valid phone number (10-14 digits).")])),
                ("date_of_birth", models.DateField()),
                ("gender", models.CharField(choices=[("F", "Female"), ("M", "Male"), ("O", "Other")], max_length=1)),
                ("blood_group", models.CharField(blank=True, choices=[("A+", "A+"), ("A-", "A-"), ("B+", "B+"), ("B-", "B-"), ("AB+", "AB+"), ("AB-", "AB-"), ("O+", "O+"), ("O-", "O-")], max_length=3)),
                ("address", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="patient_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["full_name"],
            },
        ),
        migrations.CreateModel(
            name="Appointment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("time_slot", models.CharField(choices=[("09:00", "09:00 AM"), ("09:30", "09:30 AM"), ("10:00", "10:00 AM"), ("10:30", "10:30 AM"), ("11:00", "11:00 AM"), ("11:30", "11:30 AM"), ("12:00", "12:00 PM"), ("12:30", "12:30 PM"), ("14:00", "02:00 PM"), ("14:30", "02:30 PM"), ("15:00", "03:00 PM"), ("15:30", "03:30 PM"), ("16:00", "04:00 PM"), ("16:30", "04:30 PM")], max_length=5)),
                ("reason", models.TextField(max_length=500)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("CONFIRMED", "Confirmed"), ("COMPLETED", "Completed"), ("CANCELLED", "Cancelled")], default="PENDING", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("doctor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="appointments", to="appointments.doctor")),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="appointments", to="appointments.patient")),
            ],
            options={
                "ordering": ["-date", "-time_slot"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("status", "CANCELLED"), _negated=True),
                        fields=("doctor", "date", "time_slot"),
                        name="unique_active_doctor_slot",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="MedicalReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("diagnosis", models.CharField(max_length=200)),
                ("prescription", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("follow_up_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("appointment", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="report", to="appointments.appointment")),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="appointments.patient")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
