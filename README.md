# CSIT Student Association CMS Backend

The CSIT Student Association CMS Backend is a Django REST API for managing the association's public content and internal content-management workflows. It brings events, mentors, notices, certificates, past examination papers, tenures, and committee members behind one versioned API, with JWT authentication and role-aware write permissions.

The project is designed to support a student-association dashboard: public clients can read selected published content, while CMS users and administrators can maintain the records and upload associated media.

**Live deployment:** [cms-dashbaord.onrender.com](https://cms-dashbaord.onrender.com/)

**Testing credentials:** Username: `admin` | Password: `admin`


## Capabilities

- JWT login with short-lived access tokens and rotating, blacklistable refresh tokens.
- Custom users with `admin` and `cms_user` roles.
- Event and mentor management, including event-to-mentor relationships.
- Notice management with category/status fields and image validation.
- Certificate records linked to events and protected certificate-template uploads.
- Past-paper catalogue organized by subject, semester, exam year, and model-set status.
- Tenure and member management, including cloning members from one tenure to another.
- Public content reads for events, mentors, certificates, past papers, tenures, and members.
- Page-number pagination for event, notice, and past-paper collections.
- Five-minute response caching on several read endpoints.
- File-based logging separated by domain and security concern.
- Django admin registration for the domain models.

## Technology

- Python
- Django 5.x
- Django REST Framework
- `djangorestframework-simplejwt`
- SQLite by default, with PostgreSQL-compatible database URLs through `dj-database-url` and `psycopg2-binary`
- Pillow for image uploads
- `python-dotenv` for loading a local `.env` file
- Gunicorn dependency for WSGI serving

## Architecture

The root URL configuration includes each domain app directly. All application API routes use the `/api/v1/` prefix.

```text
config/
  settings.py       Django, DRF, JWT, database, media, email, and logging settings
  urls.py           Admin route and domain URL includes
  asgi.py           ASGI entry point
  wsgi.py           WSGI entry point
apps/
  users/            Authentication, user creation, and password workflows
  core/             Shared timestamps, permissions, and pagination
  events/           Events and mentors
  notices/          Notices and announcements
  certificates/     Certificates and certificate templates
  papers/           Past examination papers
  tenure/           Tenures, members, and member cloning
manage.py            Django management entry point
media/               Uploaded files
logs/                File-based application logs
```

The custom `User` model extends Django's `AbstractUser` with a `role` field. `IsAdmin` restricts access to administrators; `IsCMSUser` permits both administrators and CMS users. Several content areas use `IsAuthenticatedOrReadOnly`, which means anonymous users can read and any authenticated user can write to those endpoints.

## Local setup

### Prerequisites

- Python 3.10 or newer
- A virtual environment
- SQLite for the default local database, or a database URL supported by `dj-database-url`

### Install and configure

```bash
git clone <repository-url>
cd cms-dashbaord

python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

The settings module loads `.env` from the project root. The supported environment variables are:

| Variable | Purpose | Default |
| --- | --- | --- |
| `SECRET_KEY` | Django signing and cryptographic key | Development-only fallback |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames | `localhost,127.0.0.1,[::1]` |
| `DATABASE_URL` | Database connection URL | Local `db.sqlite3` |

For a real deployment, set a strong `SECRET_KEY`, set `ALLOWED_HOSTS`, use a production database, and provide SMTP credentials through a secret-management system. Do not commit secrets to `.env` or source control.

### Database and server

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API is then available at `http://127.0.0.1:8000/`, and the admin site is at `http://127.0.0.1:8000/admin/`.

This repository currently contains empty migration packages rather than generated app migrations. Before using a fresh database for the domain models, create and apply migrations in the normal Django workflow:

```bash
python manage.py makemigrations users events notices certificates tenure papers core
python manage.py migrate
```

The project does not currently include automated test cases; `python manage.py test` is available for future coverage.

## Authentication

Login returns a JWT access token and refresh token:

```http
POST /api/v1/login/
Content-Type: application/json
```

```json
{
  "email": "admin@example.com",
  "password": "your-password"
}
```

Successful response (`200`):

```json
{
  "refresh": "<refresh-token>",
  "access": "<access-token>"
}
```

Send the access token on protected requests:

```http
Authorization: Bearer <access-token>
```

Access tokens last 15 minutes. Refresh tokens last 7 days; refresh rotation and blacklist-after-rotation are enabled. There is no routed logout URL in the current URL configuration, although a token-blacklisting `LogoutView` exists in the users app.

## API reference

Unless stated otherwise, validation errors return `400`, missing resources return `404`, successful deletes return `204`, and authentication failures are handled by DRF according to the request's authentication state.

### Users and authentication

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/login/` | Public | Validate email/password and issue JWT tokens. Invalid credentials return `401`. |
| `POST` | `/api/v1/users/` | Admin only | Create a user with `username`, `email`, `password`, and `role` (`admin` or `cms_user`). Passwords must be at least 8 characters. Success returns `200`. |
| `POST` | `/api/v1/users/change-password/` | CMS user or admin | Change the current user's password with `old_password` and `new_password`. Incorrect old passwords return `400`. |
| `GET` | `/api/v1/test-email/` | Public | Send an SMTP test message to the configured email account. Returns `200` on success or `500` for an email configuration/delivery failure. |
| `POST` | `/api/v1/users/forgot-password/` | Public | Accept `{ "email": "..." }` and send a reset link when the account exists. The response is intentionally generic and returns `200` for a valid email-shaped request. |
| `POST` | `/api/v1/users/reset-password/` | Public | Accept `uid`, `token`, and `new_password`; validate the Django reset token and set the new password. Invalid or expired links return `400`. |

### Events and mentors

#### Events

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/events/` | Public | List events, newest first. Supports `search`, `status`, `page`, and `page_size` (maximum `100`). |
| `POST` | `/api/v1/events/` | CMS user or admin | Create an event. Fields are `title`, `description`, `date`, optional `image`, optional `registration_link`, optional `mentors`, and optional `status` (`draft`, `published`, `completed`). `slug` is generated when omitted. Returns `201`. |
| `GET` | `/api/v1/events/<slug>/` | Public | Retrieve one event. Lookup is case-insensitive. |
| `PUT` | `/api/v1/events/<slug>/` | CMS user or admin | Replace an event. |
| `DELETE` | `/api/v1/events/<slug>/` | CMS user or admin | Delete an event. |

Event list responses use:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z",
      "title": "Annual Tech Conference",
      "slug": "annual-tech-conference",
      "description": "A student technology conference.",
      "image": null,
      "date": "2026-02-01T09:00:00Z",
      "registration_link": "https://example.com/register",
      "mentors": [],
      "status": "published"
    }
  ]
}
```

#### Mentors

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/mentors/` | Public | List mentors. |
| `POST` | `/api/v1/mentors/` | CMS user or admin | Create a mentor with `name`, `email`, `expertise`, optional `linkedin_profile`, and optional `photo`. `slug` is generated when omitted. Returns `201`. |
| `GET` | `/api/v1/mentors/<slug>/` | Public | Retrieve one mentor. |
| `PUT` | `/api/v1/mentors/<slug>/` | CMS user or admin | Replace a mentor. |
| `PATCH` | `/api/v1/mentors/<slug>/` | CMS user or admin | Partially update a mentor. |
| `DELETE` | `/api/v1/mentors/<slug>/` | CMS user or admin | Delete a mentor. |

### Notices

All notice endpoints require a CMS user or administrator, including reads.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/notices/` | List notices with `search`, `status`, `page`, and `page_size` filters. Responses are paginated. |
| `POST` | `/api/v1/notices/` | Create a notice with `title`, `description`, optional `image`, `status` (`draft` or `published`), and optional `category` (`administrative`, `academic`, or `events`). Accepts JSON or multipart form data. |
| `GET` | `/api/v1/notices/<slug>/` | Retrieve a notice. |
| `PUT` | `/api/v1/notices/<slug>/` | Replace a notice. |
| `DELETE` | `/api/v1/notices/<slug>/` | Delete a notice. |

Notice images accept JPG, JPEG, PNG, or WebP files up to 5 MB.

### Certificates and templates

Certificate reads are public. Certificate creation, update, and deletion require any authenticated user. Template operations require a CMS user or administrator. Certificate endpoints accept JSON or multipart form data where applicable.

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/certificates/` | Public | List certificates; optional `search` filters by related event title. |
| `POST` | `/api/v1/certificates/` | Authenticated user | Create a certificate with `full_name` and an event reference. Returns `201`. `certificate_id` and `issued_at` are generated by the model. |
| `GET` | `/api/v1/certificates/<certificate_id>/` | Public | Retrieve a certificate by UUID. |
| `PUT` | `/api/v1/certificates/<certificate_id>/` | Authenticated user | Replace a certificate. |
| `DELETE` | `/api/v1/certificates/<certificate_id>/` | Authenticated user | Delete a certificate. |
| `GET` | `/api/v1/certificates/templates/` | CMS user or admin | List certificate templates. |
| `POST` | `/api/v1/certificates/templates/` | CMS user or admin | Upload a template using `template_name` and required `template_file`. Returns `201`. |
| `GET` | `/api/v1/certificates/templates/<pk>/` | CMS user or admin | Retrieve a template by integer primary key. |
| `PUT` | `/api/v1/certificates/templates/<pk>/` | CMS user or admin | Replace a template. |
| `DELETE` | `/api/v1/certificates/templates/<pk>/` | CMS user or admin | Delete a template. |

### Past papers

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/past-papers/` | Public | List papers with page-number pagination (`page`, `page_size`, maximum `100`). |
| `POST` | `/api/v1/past-papers/` | Authenticated user | Create a paper with `subject_code`, `semester`, `model_set`, `exam_year`, and optional `drive_link`. `slug` is generated when omitted. Returns `201`. |
| `GET` | `/api/v1/past-papers/<slug>/` | Public | Retrieve one paper. |
| `PUT` | `/api/v1/past-papers/<slug>/` | Authenticated user | Replace a paper. |
| `DELETE` | `/api/v1/past-papers/<slug>/` | Authenticated user | Delete a paper. |

`subject_code` and `semester` must use the choices defined by the model. The combination of subject, semester, exam year, and model-set flag must be unique.

### Tenures and members

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/tenures/` | Public | List tenures with nested members. |
| `POST` | `/api/v1/tenures/` | Authenticated user | Create a tenure with `name`, `start_date`, `end_date`, and unique `slug`. Returns `201`. |
| `GET` | `/api/v1/tenures/<slug>/` | Public | Retrieve a tenure with nested members. |
| `PUT` | `/api/v1/tenures/<slug>/` | Authenticated user | Replace a tenure. |
| `DELETE` | `/api/v1/tenures/<slug>/` | Authenticated user | Delete a tenure. |
| `GET` | `/api/v1/members/` | Public | List members. |
| `POST` | `/api/v1/members/` | Authenticated user | Create a member with a tenure slug, `name`, `role`, `email`, `phone_number`, and optional image/social links. Returns `201`. |
| `GET` | `/api/v1/members/<slug>/` | Public | Retrieve one member. |
| `PUT` | `/api/v1/members/<slug>/` | Authenticated user | Replace a member. |
| `DELETE` | `/api/v1/members/<slug>/` | Authenticated user | Delete a member. |
| `POST` | `/api/v1/clone-members/<slug>/` | CMS user or admin | Clone all members from the tenure named by `source_tenure_slug` into the target tenure in the path. |

Clone example:

```http
POST /api/v1/clone-members/current-tenure/
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{
  "source_tenure_slug": "previous-tenure"
}
```

The clone operation returns `200` with a success message, `404` when either tenure does not exist, `400` when the source field is missing, or `200` with an informational message when the source tenure has no members.

## Media and storage

Uploaded files are stored below `MEDIA_ROOT` (`media/` by default):

- Event files: `media/events_templates/`
- Mentor photos: `media/mentors_photos/`
- Notice files: `media/notices/`
- Certificate templates: `media/certificate_templates/`
- Member images: `media/member_images/`

The project exposes `MEDIA_URL` as `media/`. Production media serving and persistence are deployment concerns and are not configured by a repository-level storage service.

## Operations and deployment notes

The project provides both `config.wsgi:application` and `config.asgi:application` entry points. `gunicorn` is listed as a dependency, but no Procfile, Dockerfile, CI configuration, or Render-specific deployment manifest is committed. A production deployment should therefore supply its own process command and configure environment variables, database, static/media handling, HTTPS, and secure Django settings.

The current settings use `DEBUG = True`, include a development fallback secret key, and configure SMTP directly in settings. These are development-oriented defaults and should be hardened before production use. Never expose or reuse credentials that may have been committed to a development settings file.

## Current repository limitations

- There are no generated migrations for the application models in the repository.
- The test modules are placeholders and do not currently provide automated endpoint coverage.
- Logout code exists but is not connected to a URL, so clients cannot call a logout endpoint through the current API.
- No certificate verification route or QR-code workflow is exposed.
- CORS middleware is present as a dependency but disabled in settings.
- Write permissions are intentionally documented as implemented: several non-CMS resources allow any authenticated user to create, update, or delete records.

## Administration

After creating a superuser, use `/admin/` to manage registered users, events, mentors, notices, certificates, certificate templates, past papers, tenures, and members. The admin configuration includes search, filtering, and display fields for the main content models.
