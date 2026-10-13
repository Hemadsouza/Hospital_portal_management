from datetime import date, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    AppointmentForm,
    MedicalReportForm,
    PatientRegistrationForm,
    StyledAuthenticationForm,
)
from .models import (
    DEPARTMENTS,
    MAX_ADVANCE_DAYS,
    TIME_SLOTS,
    Appointment,
    Doctor,
    MedicalReport,
    Patient,
    slot_is_past,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _patient_for(user):
    try:
        return user.patient_profile
    except Patient.DoesNotExist:
        return None


def staff_required(view):
    """Staff-only view: anonymous users go to login, non-staff get a 403."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def _safe_next(request, fallback):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return fallback


# --------------------------------------------------------------------------
# Public pages
# --------------------------------------------------------------------------
def doctor_list(request):
    doctors = Doctor.objects.filter(is_active=True).order_by("department", "name")
    selected = request.GET.get("dept", "ALL").upper()
    if selected not in dict(DEPARTMENTS):
        selected = "ALL"
    return render(
        request,
        "appointments/doctor_list.html",
        {"doctors": doctors, "departments": DEPARTMENTS, "selected_dept": selected},
    )


class PortalLoginView(LoginView):
    template_name = "appointments/login.html"
    authentication_form = StyledAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        url = self.get_redirect_url()
        if url:
            return url
        return reverse("staff_appointments" if self.request.user.is_staff else "dashboard")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome! Your patient account is ready.")
            return redirect("dashboard")
    else:
        form = PatientRegistrationForm()
    return render(request, "appointments/register.html", {"form": form})


# --------------------------------------------------------------------------
# Patient: booking + dashboard
# --------------------------------------------------------------------------
@login_required
def book_appointment(request):
    patient = _patient_for(request.user)
    if patient is None:
        messages.info(request, "Staff accounts cannot book appointments. Sign in with a patient account.")
        return redirect("doctor_list")

    if request.method == "POST":
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = patient
            try:
                with transaction.atomic():
                    appointment.save()
            except IntegrityError:
                # Two people raced for the same slot; the DB constraint caught it.
                form.add_error(None, "That slot was just booked by someone else. Please pick another time.")
            else:
                messages.success(
                    request,
                    f"Appointment requested with {appointment.doctor.name} on "
                    f"{appointment.date:%d %b %Y} at {appointment.slot_label}. Status: Pending.",
                )
                return redirect("dashboard")
    else:
        initial = {}
        doctor_id = request.GET.get("doctor", "")
        if doctor_id.isdigit():
            initial["doctor"] = int(doctor_id)
        form = AppointmentForm(initial=initial)

    return render(
        request,
        "appointments/book.html",
        {"form": form, "max_days": MAX_ADVANCE_DAYS},
    )


@login_required
@require_GET
def slots_api(request):
    """JSON list of slots (available / booked / past) for a doctor on a date."""
    try:
        doctor = Doctor.objects.get(pk=int(request.GET.get("doctor", "")), is_active=True)
        day = date.fromisoformat(request.GET.get("date", ""))
    except (ValueError, Doctor.DoesNotExist):
        return JsonResponse({"error": "Choose a doctor and a valid date."}, status=400)

    today = timezone.localdate()
    if day < today or day > today + timedelta(days=MAX_ADVANCE_DAYS):
        return JsonResponse(
            {"error": f"Choose a date between today and {MAX_ADVANCE_DAYS} days from now."},
            status=400,
        )

    if not doctor.works_on(day):
        return JsonResponse(
            {
                "closed": True,
                "slots": [],
                "message": f"{doctor.name} does not see patients on {day.strftime('%A')}s. "
                f"Available: {doctor.available_days_display}.",
            }
        )

    booked = set(
        Appointment.objects.filter(doctor=doctor, date=day)
        .exclude(status=Appointment.CANCELLED)
        .values_list("time_slot", flat=True)
    )
    slots = []
    for value, label in TIME_SLOTS:
        if value in booked:
            state = "booked"
        elif slot_is_past(day, value):
            state = "past"
        else:
            state = "available"
        slots.append({"value": value, "label": label, "state": state})
    return JsonResponse({"closed": False, "slots": slots})


@login_required
def dashboard(request):
    patient = _patient_for(request.user)
    if patient is None:
        messages.info(request, "This is a staff account. Use the staff console to manage appointments.")
        return redirect("staff_appointments" if request.user.is_staff else "doctor_list")

    today = timezone.localdate()
    base = patient.appointments.select_related("doctor", "report")
    upcoming = base.filter(
        date__gte=today, status__in=[Appointment.PENDING, Appointment.CONFIRMED]
    ).order_by("date", "time_slot")
    past = base.exclude(pk__in=upcoming.values("pk")).order_by("-date", "-time_slot")
    stats = base.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=Appointment.PENDING)),
        confirmed=Count("id", filter=Q(status=Appointment.CONFIRMED)),
        completed=Count("id", filter=Q(status=Appointment.COMPLETED)),
    )
    return render(
        request,
        "appointments/dashboard.html",
        {"patient": patient, "upcoming": upcoming, "past": past, "stats": stats},
    )


@login_required
@require_POST
def cancel_appointment(request, pk):
    patient = _patient_for(request.user)
    appointment = get_object_or_404(Appointment, pk=pk, patient=patient) if patient else None
    if appointment is None:
        raise PermissionDenied
    if appointment.patient_can_cancel:
        appointment.status = Appointment.CANCELLED
        appointment.save(update_fields=["status"])
        messages.success(request, "Your appointment has been cancelled.")
    else:
        messages.error(request, "This appointment can no longer be cancelled.")
    return redirect("dashboard")


# --------------------------------------------------------------------------
# Staff console
# --------------------------------------------------------------------------
@staff_required
def staff_appointments(request):
    status = request.GET.get("status", "ALL").upper()
    query = request.GET.get("q", "").strip()

    appointments = Appointment.objects.select_related("patient", "doctor", "report")
    counts = appointments.aggregate(
        ALL=Count("id"),
        PENDING=Count("id", filter=Q(status=Appointment.PENDING)),
        CONFIRMED=Count("id", filter=Q(status=Appointment.CONFIRMED)),
        COMPLETED=Count("id", filter=Q(status=Appointment.COMPLETED)),
        CANCELLED=Count("id", filter=Q(status=Appointment.CANCELLED)),
    )
    if status in dict(Appointment.STATUS_CHOICES):
        appointments = appointments.filter(status=status)
    else:
        status = "ALL"
    if query:
        appointments = appointments.filter(
            Q(patient__full_name__icontains=query)
            | Q(doctor__name__icontains=query)
            | Q(reason__icontains=query)
        )
    tabs = [("ALL", "All")] + Appointment.STATUS_CHOICES
    return render(
        request,
        "appointments/staff_appointments.html",
        {
            "appointments": appointments.order_by("date", "time_slot")[:200],
            "tabs": [(code, label, counts[code]) for code, label in tabs],
            "status": status,
            "query": query,
        },
    )


@staff_required
@require_POST
def staff_update_status(request, pk):
    appointment = get_object_or_404(Appointment.objects.select_related("doctor", "patient"), pk=pk)
    new_status = request.POST.get("status", "")
    allowed = Appointment.ALLOWED_TRANSITIONS.get(appointment.status, set())
    back = _safe_next(request, reverse("staff_appointments"))

    if new_status not in allowed:
        messages.error(
            request,
            f"Cannot change a {appointment.get_status_display().lower()} appointment to "
            f"{new_status.lower() or 'that status'}.",
        )
        return redirect(back)

    appointment.status = new_status
    try:
        with transaction.atomic():
            appointment.save(update_fields=["status"])
    except IntegrityError:
        messages.error(request, "Could not update: that slot is held by another active appointment.")
    else:
        messages.success(
            request,
            f"{appointment.patient.full_name}'s appointment is now {appointment.get_status_display()}.",
        )
    return redirect(back)


@staff_required
def staff_report(request, pk):
    appointment = get_object_or_404(Appointment.objects.select_related("doctor", "patient"), pk=pk)
    if appointment.status != Appointment.COMPLETED:
        messages.error(request, "Mark the appointment as Completed before adding a medical report.")
        return redirect("staff_appointments")

    try:
        report = appointment.report
    except MedicalReport.DoesNotExist:
        report = MedicalReport(appointment=appointment, patient=appointment.patient)

    if request.method == "POST":
        form = MedicalReportForm(request.POST, instance=report)
        if form.is_valid():
            form.save()
            messages.success(request, "Medical report saved.")
            return redirect("staff_appointments")
    else:
        form = MedicalReportForm(instance=report)
    return render(
        request,
        "appointments/staff_report.html",
        {"form": form, "appointment": appointment},
    )
