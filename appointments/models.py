from datetime import date, datetime

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

# --------------------------------------------------------------------------
# Constants shared by models, forms and views
# --------------------------------------------------------------------------
DEPARTMENTS = [
    ("CARDIOLOGY", "Cardiology"),
    ("PEDIATRICS", "Pediatrics"),
    ("ORTHOPEDICS", "Orthopedics"),
    ("NEUROLOGY", "Neurology"),
]

# Index in this list == date.weekday() (Monday is 0).
WEEKDAYS = [
    ("MON", "Monday"),
    ("TUE", "Tuesday"),
    ("WED", "Wednesday"),
    ("THU", "Thursday"),
    ("FRI", "Friday"),
    ("SAT", "Saturday"),
    ("SUN", "Sunday"),
]
WEEKDAY_CODES = [code for code, _ in WEEKDAYS]

# 30-minute slots: 09:00-13:00 and 14:00-17:00 (lunch break 13:00-14:00).
TIME_SLOTS = [
    ("09:00", "09:00 AM"),
    ("09:30", "09:30 AM"),
    ("10:00", "10:00 AM"),
    ("10:30", "10:30 AM"),
    ("11:00", "11:00 AM"),
    ("11:30", "11:30 AM"),
    ("12:00", "12:00 PM"),
    ("12:30", "12:30 PM"),
    ("14:00", "02:00 PM"),
    ("14:30", "02:30 PM"),
    ("15:00", "03:00 PM"),
    ("15:30", "03:30 PM"),
    ("16:00", "04:00 PM"),
    ("16:30", "04:30 PM"),
]

MAX_ADVANCE_DAYS = 60


def slot_is_past(day: date, slot_value: str) -> bool:
    """True if the given slot on `day` has already started (clinic local time)."""
    hour, minute = (int(part) for part in slot_value.split(":"))
    start = timezone.make_aware(datetime(day.year, day.month, day.day, hour, minute))
    return start <= timezone.now()


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class Doctor(models.Model):
    name = models.CharField(max_length=120)
    department = models.CharField(max_length=20, choices=DEPARTMENTS)
    specialization = models.CharField(max_length=120)
    consultation_fee = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(0)]
    )
    # Comma separated weekday codes, e.g. "MON,WED,FRI"
    available_days = models.CharField(max_length=40, default="MON,TUE,WED,THU,FRI")
    experience_years = models.PositiveSmallIntegerField(default=5)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["department", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_department_display()})"

    @property
    def available_days_list(self):
        return [code for code in self.available_days.split(",") if code]

    @property
    def available_days_display(self):
        names = dict(WEEKDAYS)
        return ", ".join(names[c][:3] for c in self.available_days_list if c in names)

    def works_on(self, day: date) -> bool:
        return WEEKDAY_CODES[day.weekday()] in self.available_days_list

    @property
    def initials(self):
        parts = [p for p in self.name.replace("Dr.", "").split() if p]
        return "".join(p[0] for p in parts[:2]).upper()


class Patient(models.Model):
    GENDER_CHOICES = [("F", "Female"), ("M", "Male"), ("O", "Other")]
    BLOOD_GROUPS = [
        ("A+", "A+"), ("A-", "A-"), ("B+", "B+"), ("B-", "B-"),
        ("AB+", "AB+"), ("AB-", "AB-"), ("O+", "O+"), ("O-", "O-"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="patient_profile"
    )
    full_name = models.CharField(max_length=120)
    phone = models.CharField(
        max_length=15,
        validators=[RegexValidator(r"^\+?\d{10,14}$", "Enter a valid phone number (10-14 digits).")],
    )
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUPS, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Appointment(models.Model):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (CONFIRMED, "Confirmed"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
    ]
    # Which status changes staff may make from each status.
    ALLOWED_TRANSITIONS = {
        PENDING: {CONFIRMED, CANCELLED},
        CONFIRMED: {COMPLETED, CANCELLED},
        COMPLETED: set(),
        CANCELLED: set(),
    }

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="appointments")
    date = models.DateField()
    time_slot = models.CharField(max_length=5, choices=TIME_SLOTS)
    reason = models.TextField(max_length=500)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-time_slot"]
        constraints = [
            # Database-level guard against double booking. Cancelled
            # appointments free their slot, so they are excluded.
            models.UniqueConstraint(
                fields=["doctor", "date", "time_slot"],
                condition=~Q(status="CANCELLED"),
                name="unique_active_doctor_slot",
            )
        ]

    def __str__(self):
        return f"{self.patient} with {self.doctor.name} on {self.date} {self.time_slot}"

    @property
    def slot_label(self):
        return dict(TIME_SLOTS).get(self.time_slot, self.time_slot)

    @property
    def is_open(self):
        return self.status in (self.PENDING, self.CONFIRMED)

    @property
    def patient_can_cancel(self):
        return self.is_open and not slot_is_past(self.date, self.time_slot)

    @property
    def next_statuses(self):
        """(value, label) pairs staff can move this appointment to."""
        labels = dict(self.STATUS_CHOICES)
        order = [self.CONFIRMED, self.COMPLETED, self.CANCELLED]
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, set())
        return [(s, labels[s]) for s in order if s in allowed]


class MedicalReport(models.Model):
    appointment = models.OneToOneField(
        Appointment, on_delete=models.CASCADE, related_name="report"
    )
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="reports")
    diagnosis = models.CharField(max_length=200)
    prescription = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.patient_id and self.appointment_id:
            self.patient = self.appointment.patient
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Report for {self.patient} - {self.diagnosis}"
