from django.contrib import admin, messages

from .forms import DoctorAdminForm
from .models import Appointment, Doctor, MedicalReport, Patient

admin.site.site_header = "Medvale Hospital Administration"
admin.site.site_title = "Medvale Admin"
admin.site.index_title = "Manage doctors, patients and appointments"


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    form = DoctorAdminForm
    list_display = ("name", "department", "specialization", "consultation_fee", "available_days", "is_active")
    list_filter = ("department", "is_active")
    list_editable = ("is_active",)
    search_fields = ("name", "specialization")


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "gender", "blood_group", "date_of_birth", "user")
    search_fields = ("full_name", "phone", "user__username")
    list_filter = ("gender", "blood_group")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "date", "time_slot", "status", "created_at")
    list_filter = ("status", "date", "doctor__department", "doctor")
    search_fields = ("patient__full_name", "doctor__name", "reason")
    date_hierarchy = "date"
    actions = ["confirm_selected", "complete_selected", "cancel_selected"]

    def _move(self, request, queryset, from_statuses, to_status, label):
        updated = queryset.filter(status__in=from_statuses).update(status=to_status)
        self.message_user(request, f"{updated} appointment(s) {label}.", messages.SUCCESS)

    @admin.action(description="Confirm selected pending appointments")
    def confirm_selected(self, request, queryset):
        self._move(request, queryset, [Appointment.PENDING], Appointment.CONFIRMED, "confirmed")

    @admin.action(description="Mark selected confirmed appointments as completed")
    def complete_selected(self, request, queryset):
        self._move(request, queryset, [Appointment.CONFIRMED], Appointment.COMPLETED, "completed")

    @admin.action(description="Cancel selected open appointments")
    def cancel_selected(self, request, queryset):
        self._move(
            request, queryset, [Appointment.PENDING, Appointment.CONFIRMED], Appointment.CANCELLED, "cancelled"
        )


@admin.register(MedicalReport)
class MedicalReportAdmin(admin.ModelAdmin):
    list_display = ("patient", "appointment", "diagnosis", "follow_up_date", "created_at")
    search_fields = ("patient__full_name", "diagnosis")
    readonly_fields = ("patient",)
