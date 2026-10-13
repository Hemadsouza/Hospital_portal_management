"""
Create an admin (superuser) from environment variables - used on Render, where
there is no interactive shell on the free plan.

Required env vars to create the user:
    DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_PASSWORD
Optional:
    DJANGO_SUPERUSER_EMAIL
    SEED_DEMO_DATA=true   -> also loads demo doctors/patients/appointments

Passwords are read from the environment, never hard-coded in the repository.
"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hospital_portal.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")

if username and password:
    if User.objects.filter(username=username).exists():
        print(f"Superuser '{username}' already exists - nothing to do.")
    else:
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f"Superuser '{username}' created.")
else:
    print("DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD not set - skipping superuser creation.")

if os.environ.get("SEED_DEMO_DATA", "").lower() == "true":
    call_command("seed_demo")
