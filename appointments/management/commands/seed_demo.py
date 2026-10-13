"""
Create demo doctors, patients and appointments so every feature can be shown.

    python manage.py seed_demo

Safe to run more than once (it skips data that already exists).
Demo login passwords come from DEMO_USER_PASSWORD (default: Demo@12345,
for LOCAL use only - set your own value on Render).
"""
import os
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from appointments.models import Appointment, Doctor, MedicalReport, Patient

User = get_user_model()

DOCTORS = [
    ("Dr. Meera Iyer", "CARDIOLOGY", "Interventional Cardiology", 900, "MON,TUE,THU,FRI", 14,
     "Leads the cath lab and focuses on heart attack recovery and stent care."),
    ("Dr. Arjun Nair", "CARDIOLOGY", "Cardiac Electrophysiology", 1100, "TUE,WED,FRI,SAT", 11,
     "Treats rhythm disorders, palpitations and pacemaker follow-up."),
    ("Dr. Sana Qureshi", "PEDIATRICS", "Neonatology", 700, "MON,TUE,WED,THU,FRI", 9,
     "Cares for newborns and premature infants through their first year."),
    ("Dr. Vikram Desai", "PEDIATRICS", "General Pediatrics", 600, "MON,WED,FRI,SAT", 12,
     "Child wellness checks, vaccinations and common childhood illness."),
    ("Dr. Kavita Reddy", "ORTHOPEDICS", "Joint Replacement", 1000, "MON,WED,THU,SAT", 16,
     "Hip and knee replacement with a focus on faster mobility after surgery."),
    ("Dr. Rohan Kulkarni", "ORTHOPEDICS", "Sports Injury", 850, "TUE,THU,FRI,SAT", 8,
     "Ligament, tendon and fracture care for athletes and active adults."),
    ("Dr. Farhan Ali", "NEUROLOGY", "Stroke & Epilepsy", 1200, "MON,TUE,WED,FRI", 15,
     "Acute stroke follow-up, seizure management and migraine treatment."),
    ("Dr. Lakshmi Menon", "NEUROLOGY", "Movement Disorders", 1050, "WED,THU,FRI,SAT", 10,
     "Parkinson's disease, tremors and neuromuscular conditions."),
]

WEEKDAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def next_working_day(doctor, start):
    day = start
    while WEEKDAY_CODES[day.weekday()] not in doctor.available_days_list:
        day += timedelta(days=1)
    return day


def previous_working_day(doctor, start):
    day = start
    while WEEKDAY_CODES[day.weekday()] not in doctor.available_days_list:
        day -= timedelta(days=1)
    return day


class Command(BaseCommand):
    help = "Seed demo doctors, patients, a staff user and sample appointments."

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_USER_PASSWORD", "Demo@12345")
        today = timezone.localdate()

        # Doctors -----------------------------------------------------------
        doctors = []
        for name, dept, spec, fee, days, years, bio in DOCTORS:
            doctor, _ = Doctor.objects.get_or_create(
                name=name,
                defaults=dict(
                    department=dept, specialization=spec, consultation_fee=fee,
                    available_days=days, experience_years=years, bio=bio,
                ),
            )
            doctors.append(doctor)
        self.stdout.write(self.style.SUCCESS(f"Doctors ready: {len(doctors)}"))

        # Staff user ----------------------------------------------------------
        if not User.objects.filter(username="staff").exists():
            User.objects.create_user("staff", "staff@example.com", password, is_staff=True,
                                     first_name="Front", last_name="Desk")
            self.stdout.write("Created staff user 'staff' (can use the staff console).")

        # Patients ------------------------------------------------------------
        patients = []
        for username, full, phone, dob, gender, blood in [
            ("patient", "Ananya Rao", "9876543210", date(1992, 4, 18), "F", "B+"),
            ("rahul", "Rahul Mehta", "9123456780", date(1985, 11, 2), "M", "O+"),
        ]:
            user, created = User.objects.get_or_create(
                username=username,
                defaults=dict(email=f"{username}@example.com",
                              first_name=full.split()[0], last_name=full.split()[1]),
            )
            if created:
                user.set_password(password)
                user.save()
            patient, _ = Patient.objects.get_or_create(
                user=user,
                defaults=dict(full_name=full, phone=phone, date_of_birth=dob,
                              gender=gender, blood_group=blood, address="Hyderabad, Telangana"),
            )
            patients.append(patient)
        ananya, rahul = patients

        if Appointment.objects.exists():
            self.stdout.write("Appointments already exist - skipping sample appointments.")
            return

        # Appointments (upcoming, past and cancelled) -------------------------
        def make(patient, doctor, day, slot, reason, status):
            return Appointment.objects.create(
                patient=patient, doctor=doctor, date=day, time_slot=slot, reason=reason, status=status
            )

        cardio, ep, neo, peds, joint, sports, stroke, move = doctors

        # Upcoming for Ananya
        make(ananya, cardio, next_working_day(cardio, today + timedelta(days=2)), "10:00",
             "Chest tightness during evening walks", Appointment.CONFIRMED)
        make(ananya, stroke, next_working_day(stroke, today + timedelta(days=4)), "11:30",
             "Recurring migraines for the past month", Appointment.PENDING)
        make(ananya, peds, next_working_day(peds, today + timedelta(days=6)), "15:00",
             "Vaccination check for my 3-year-old", Appointment.PENDING)

        # Same doctors/dates booked by another patient so some slots show as booked
        d1 = next_working_day(cardio, today + timedelta(days=2))
        make(rahul, cardio, d1, "09:30", "Follow-up after stress test", Appointment.CONFIRMED)
        make(rahul, cardio, d1, "10:30", "High blood pressure review", Appointment.PENDING)
        make(rahul, cardio, d1, "14:00", "Palpitations at night", Appointment.CONFIRMED)
        d2 = next_working_day(joint, today + timedelta(days=3))
        make(rahul, joint, d2, "09:00", "Knee pain when climbing stairs", Appointment.CONFIRMED)
        make(rahul, joint, d2, "09:30", "Second opinion on knee MRI", Appointment.PENDING)

        # Past / cancelled for Ananya
        past_day = previous_working_day(sports, today - timedelta(days=9))
        done = make(ananya, sports, past_day, "11:00", "Ankle sprain after a fall", Appointment.COMPLETED)
        MedicalReport.objects.create(
            appointment=done, patient=ananya,
            diagnosis="Grade 1 lateral ankle sprain",
            prescription="Rest, ice 15 min x 3 daily, elastic bandage, ibuprofen 400 mg after food for 5 days.",
            notes="No fracture suspected. Start light range-of-motion exercises after 3 days.",
            follow_up_date=today + timedelta(days=14),
        )
        done2 = make(ananya, neo, previous_working_day(neo, today - timedelta(days=20)), "09:30",
                     "Newborn jaundice check for my nephew", Appointment.COMPLETED)
        MedicalReport.objects.create(
            appointment=done2, patient=ananya,
            diagnosis="Physiological jaundice, resolving",
            prescription="Frequent feeding every 2-3 hours and morning sunlight exposure.",
            notes="Bilirubin trending down. Review only if skin colour worsens.",
        )
        make(ananya, ep, previous_working_day(ep, today - timedelta(days=5)), "14:30",
             "Fast heartbeat episodes", Appointment.CANCELLED)

        self.stdout.write(self.style.SUCCESS("Sample appointments created."))
        self.stdout.write(
            "Demo logins -> patient: 'patient' / 'rahul', staff: 'staff' "
            "(password = DEMO_USER_PASSWORD, default Demo@12345)."
        )
