from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction
from django.utils import timezone

from .models import (
    MAX_ADVANCE_DAYS,
    WEEKDAYS,
    Appointment,
    Doctor,
    MedicalReport,
    Patient,
    slot_is_past,
)

User = get_user_model()


def _style_fields(form):
    """Apply Bootstrap 5 classes to every widget in a form."""
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.HiddenInput):
            continue
        if isinstance(widget, (forms.CheckboxSelectMultiple, forms.CheckboxInput)):
            continue
        css = "form-select" if isinstance(widget, forms.Select) else "form-control"
        widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


# --------------------------------------------------------------------------
# Auth forms
# --------------------------------------------------------------------------
class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class PatientRegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=120)
    email = forms.EmailField()
    phone = forms.CharField(
        max_length=15,
        validators=Patient._meta.get_field("phone").validators,
        help_text="10-14 digits, optional + prefix.",
    )
    date_of_birth = forms.DateField(
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    gender = forms.ChoiceField(choices=[("", "Select")] + Patient.GENDER_CHOICES)
    blood_group = forms.ChoiceField(
        choices=[("", "Not sure")] + Patient.BLOOD_GROUPS, required=False
    )
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    field_order = [
        "full_name", "email", "phone", "date_of_birth", "gender", "blood_group",
        "address", "username", "password1", "password2",
    ]

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)
        self.fields["date_of_birth"].widget.attrs["max"] = timezone.localdate().isoformat()

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        if dob >= timezone.localdate():
            raise forms.ValidationError("Date of birth must be in the past.")
        return dob

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        first, _, last = self.cleaned_data["full_name"].strip().partition(" ")
        user.first_name, user.last_name = first, last
        if commit:
            with transaction.atomic():
                user.save()
                Patient.objects.create(
                    user=user,
                    full_name=self.cleaned_data["full_name"].strip(),
                    phone=self.cleaned_data["phone"],
                    date_of_birth=self.cleaned_data["date_of_birth"],
                    gender=self.cleaned_data["gender"],
                    blood_group=self.cleaned_data["blood_group"],
                    address=self.cleaned_data["address"],
                )
        return user


# --------------------------------------------------------------------------
# Appointment booking (ModelForm + server-side validation)
# --------------------------------------------------------------------------
class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["doctor", "date", "time_slot", "reason"]
        widgets = {
            "date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "time_slot": forms.HiddenInput(),
            "reason": forms.Textarea(
                attrs={"rows": 3, "maxlength": 500, "placeholder": "Briefly describe your symptoms or the purpose of the visit"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["doctor"].queryset = Doctor.objects.filter(is_active=True)
        self.fields["doctor"].empty_label = "Select a doctor"
        self.fields["date"].widget.attrs["min"] = today.isoformat()
        self.fields["date"].widget.attrs["max"] = (today + timedelta(days=MAX_ADVANCE_DAYS)).isoformat()
        self.fields["time_slot"].error_messages["required"] = "Please pick a time slot."
        _style_fields(self)

    def clean_date(self):
        day = self.cleaned_data["date"]
        today = timezone.localdate()
        if day < today:
            raise forms.ValidationError("Appointment date cannot be in the past.")
        if day > today + timedelta(days=MAX_ADVANCE_DAYS):
            raise forms.ValidationError(
                f"Appointments can be booked up to {MAX_ADVANCE_DAYS} days in advance."
            )
        return day

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if len(reason) < 5:
            raise forms.ValidationError("Please describe the reason for your visit (at least 5 characters).")
        return reason

    def clean(self):
        cleaned = super().clean()
        doctor = cleaned.get("doctor")
        day = cleaned.get("date")
        slot = cleaned.get("time_slot")
        if doctor and day:
            if not doctor.works_on(day):
                self.add_error(
                    "date",
                    f"{doctor.name} does not see patients on {day.strftime('%A')}s "
                    f"(available: {doctor.available_days_display}).",
                )
                return cleaned
            if slot:
                if slot_is_past(day, slot):
                    self.add_error("time_slot", "That time has already passed. Choose a later slot.")
                elif (
                    Appointment.objects.filter(doctor=doctor, date=day, time_slot=slot)
                    .exclude(status=Appointment.CANCELLED)
                    .exists()
                ):
                    self.add_error(
                        "time_slot",
                        "This slot is already booked for the selected doctor. Please choose another.",
                    )
        return cleaned


# --------------------------------------------------------------------------
# Staff forms
# --------------------------------------------------------------------------
class MedicalReportForm(forms.ModelForm):
    class Meta:
        model = MedicalReport
        fields = ["diagnosis", "prescription", "notes", "follow_up_date"]
        widgets = {
            "prescription": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "follow_up_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)

    def clean_follow_up_date(self):
        day = self.cleaned_data.get("follow_up_date")
        if day and day < timezone.localdate():
            raise forms.ValidationError("Follow-up date cannot be in the past.")
        return day


# --------------------------------------------------------------------------
# Admin helper: tick-box weekday selector for Doctor.available_days
# --------------------------------------------------------------------------
class DoctorAdminForm(forms.ModelForm):
    available_days = forms.MultipleChoiceField(
        choices=WEEKDAYS,
        widget=forms.CheckboxSelectMultiple,
        help_text="Days this doctor sees patients.",
    )

    class Meta:
        model = Doctor
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["available_days"] = self.instance.available_days_list

    def clean_available_days(self):
        chosen = set(self.cleaned_data["available_days"])
        return ",".join(code for code, _ in WEEKDAYS if code in chosen)
