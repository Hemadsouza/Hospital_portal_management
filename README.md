# Medvale Hospital - Patient Appointment Management Portal

Django 5.2/6.x full-stack capstone: patients browse doctors by department, book
30-minute slots (booked/available shown live), and track appointment status.
Staff confirm, cancel and complete appointments and add medical reports.

Stack: HTML5, CSS3, JavaScript (ES6), Bootstrap 5, Python 3.11+, Django ORM,
SQLite (db.sqlite3), Gunicorn, WhiteNoise, Render.

## Run locally (Windows / macOS / Linux)

```bash
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # macOS / Linux

pip install -r requirements.txt
python manage.py makemigrations  # should say "No changes detected"
python manage.py migrate         # creates db.sqlite3
python manage.py seed_demo       # demo doctors, patients, appointments
python manage.py createsuperuser # your own admin login
python manage.py runserver
```

Open http://127.0.0.1:8000/

Demo logins created by `seed_demo` (password `Demo@12345` locally, or whatever
you put in the DEMO_USER_PASSWORD environment variable):

| Role    | Username  | Where to go                  |
|---------|-----------|------------------------------|
| Patient | `patient` | /dashboard/, /book/          |
| Patient | `rahul`   | /dashboard/                  |
| Staff   | `staff`   | /staff/appointments/         |
| Admin   | the one you created | /admin/            |

## Pages

| URL                          | Purpose                                            |
|------------------------------|----------------------------------------------------|
| `/`                          | Doctor list, JS department filter + search, modal  |
| `/register/` `/login/`       | Patient sign-up and sign-in                        |
| `/book/`                     | Booking form with interactive slot picker          |
| `/api/slots/`                | JSON used by the slot picker                       |
| `/dashboard/`                | Upcoming and past appointments, cancel, reports    |
| `/staff/appointments/`       | Staff: confirm / cancel / complete, add reports    |
| `/admin/`                    | Django admin for all four models                   |

## Business rules (enforced on the server)

* No double booking: form validation **and** a database UniqueConstraint on
  (doctor, date, time_slot) for non-cancelled appointments. Cancelled
  appointments free their slot.
* Date cannot be in the past or more than 60 days ahead; the doctor must work
  that weekday; past time slots on today's date are rejected.
* Status flow: Pending -> Confirmed -> Completed, and Pending/Confirmed -> Cancelled.
* All POST forms use `{% csrf_token %}`; staff pages require `is_staff`.

## Deploy to Render

1. Push to GitHub (`git add .`, `git commit`, `git push origin main`).
2. Render dashboard -> New + -> **Blueprint** -> pick the repo (it reads `render.yaml`).
3. Render asks for `DJANGO_SUPERUSER_PASSWORD` and `DEMO_USER_PASSWORD`; enter your own values.
4. Wait for the build, then open the `https://<name>.onrender.com` URL.

SQLite on Render's free plan is ephemeral: data resets on restart/redeploy.
That is why `SEED_DEMO_DATA=true` reloads the demo data at each start.
