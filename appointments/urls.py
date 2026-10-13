from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.doctor_list, name="doctor_list"),
    path("register/", views.register, name="register"),
    path("login/", views.PortalLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("book/", views.book_appointment, name="book"),
    path("api/slots/", views.slots_api, name="slots_api"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("appointments/<int:pk>/cancel/", views.cancel_appointment, name="cancel_appointment"),
    path("staff/appointments/", views.staff_appointments, name="staff_appointments"),
    path("staff/appointments/<int:pk>/status/", views.staff_update_status, name="staff_update_status"),
    path("staff/appointments/<int:pk>/report/", views.staff_report, name="staff_report"),
]
