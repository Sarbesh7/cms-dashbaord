# CSIT Student Association CMS Backend

The CSIT Student Association CMS Backend is a Django REST Framework application for managing association content and committee data. It provides a public API for events, mentors, notices, certificates, past papers, tenures, members, memberships, and alumni, together with authenticated content-management operations.

**Live deployment:** [cms-dashbaord.onrender.com](https://cms-dashbaord.onrender.com/)

The empty URL (`/`) renders the API dashboard at [apps/core/templates/dashboard/index.html](apps/core/templates/dashboard/index.html). The Django admin is available at `/admin/`.

## Capabilities

- Cookie-based JWT login, refresh, logout, and password reset workflows.
- Custom users with `admin` and `cms_user` roles.
- Event and mentor management with images, filtering, pagination, and caching.
- Notice management with draft/published status, categories, images, filtering, and caching.
- Certificate records and protected certificate-template uploads.
- Past-paper catalogue organized by subject, semester, model-set flag, and exam year.
- Tenures, members, tenure memberships, alumni, and member cloning.
- Public read access for selected content and authenticated write access according to each view's permission class.
- Five-minute caching on selected list and detail endpoints.
- Domain-specific file logging locally and console logging when `RENDER=true`.
- Django admin registration for the main domain models.

## Technology

- Python 3.10+
- Django 5.x
- Django REST Framework
- `djangorestframework-simplejwt`
- `dj-database-url` with SQLite development support and PostgreSQL-compatible database URLs
- Pillow for image processing
- WhiteNoise for static files
- `django-cors-headers`
- Cloudinary and `django-cloudinary-storage` for optional media storage
- Gunicorn dependency for WSGI serving

## Project structure

```text
config/
  settings/
    base.py          Shared Django, DRF, JWT, database, media, and logging settings
    development.py   Local development settings and .env loading
    production.py    Production settings and environment-based configuration
  urls.py             Admin, dashboard, and application URL includes
  asgi.py             ASGI entry point
  wsgi.py             WSGI entry point
apps/
  users/              Authentication, users, password workflows
  core/               Shared models, permissions, caching, pagination, dashboard template
  events/             Events and mentors
  notices/            Notices and announcements
  certificates/       Certificates and certificate templates
  papers/             Past examination papers
  tenure/             Tenures, members, memberships, and alumni
manage.py              Django management entry point
db.sqlite3             Local SQLite database
media/                 Uploaded media files
logs/                  Local application logs
requirements.txt       Python dependencies
```

Each domain app contains its models, serializers, views, URLs, admin registration, tests, and migrations. Generated migrations are present for users, events, notices, certificates, papers, and tenure. The core app currently has no model migrations.

## Local setup

### Prerequisites

- Python 3.10 or newer
- A virtual environment
- SQLite for the default local database, or a database URL supported by `dj-database-url`

### Install and configure

```bash
git clone <repository-url>
cd cms-dashbaord

python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# macOS/Linux
# source venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Development uses `config.settings.development`, which loads `.env` from the project root. Important development variables include:

| Variable | Purpose | Default |
| --- | --- | --- |
| `SECRET_KEY` | Django signing key | Development-only fallback |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1,[::1]` |
| `DATABASE_URL` | Database connection URL | Local `db.sqlite3` |
| `USE_CLOUDINARY` | Enable Cloudinary media storage | `False` |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name | None |
| `CLOUDINARY_API_KEY` | Cloudinary API key | None |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret | None |

Do not commit real credentials or secret keys to source control.

### Database and server

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The local application is available at `http://127.0.0.1:8000/`. The dashboard is at `/`, the API uses `/api/v1/`, and the admin site is at `/admin/`.

To use production settings locally, provide `DJANGO_SECRET_KEY`, `DATABASE_URL`, and the required production environment variables, then run commands with:

```bash
python manage.py check --settings=config.settings.production
```

## Authentication

Login is available at:

```http
POST /api/v1/login/
Content-Type: application/json
```

The login request accepts the credentials expected by the users view. On success, the view sets `access_token` and `refresh_token` cookies and returns user information in JSON. The configured DRF authentication class reads the access JWT from the `access_token` cookie.

The configured token lifetimes are:

- Access token: 15 minutes
- Refresh token: 7 days
- Refresh rotation: enabled
- Blacklisting after rotation: enabled

The relevant authentication endpoints are:

| Method | Endpoint | Access |
| --- | --- | --- |
| `POST` | `/api/v1/login/` | Public |
| `POST` | `/api/v1/users/refresh-token/` | Uses refresh cookie |
| `POST` | `/api/v1/users/logout/` | Authenticated user |
| `POST` | `/api/v1/users/change-password/` | CMS user or admin |
| `POST` | `/api/v1/users/reset-password/` | Admin only |

The email-test and forgot-password routes are not currently enabled in `apps/users/urls.py`.

## API reference

All application API routes use the `/api/v1/` prefix. Paginated endpoints use page-number pagination with a default page size of `40`, a configurable `page_size` query parameter, and a maximum page size of `100`, as defined by `StandardPagination`.

### Users

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET`, `POST` | `/api/v1/users/` | Admin only | List or create users. |
| `GET` | `/api/v1/users/<user_id>/` | Admin only | Retrieve a user. |
| `POST` | `/api/v1/users/change-password/` | CMS user or admin | Change the current user's password. |
| `POST` | `/api/v1/users/reset-password/` | Admin only | Reset a user's password. |

Users support the `admin` and `cms_user` roles. The custom user model extends Django's `AbstractUser` and supports an optional profile picture.

### Events and mentors

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/events/` | Public | List events with search, status, category, ID, date, ordering, pagination, and caching. |
| `POST` | `/api/v1/events/` | CMS user or admin | Create an event. |
| `GET` | `/api/v1/events/<slug>/` | Public | Retrieve an event. |
| `PUT`, `PATCH`, `DELETE` | `/api/v1/events/<slug>/` | CMS user or admin | Modify or delete an event. |
| `GET` | `/api/v1/mentors/` | Public | List mentors with search, ID, ordering, pagination, and caching. |
| `POST` | `/api/v1/mentors/` | CMS user or admin | Create a mentor. |
| `GET` | `/api/v1/mentors/<slug>/` | Public | Retrieve a mentor. |
| `PUT`, `PATCH`, `DELETE` | `/api/v1/mentors/<slug>/` | CMS user or admin | Modify or delete a mentor. |

Events support dates, status, category, tags, organizer, location, seat capacity, registration information, images, an optional tenure, and mentor relationships. Mentors support contact, expertise, LinkedIn, photo, and optional tenure-member information.

### Notices

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/notices/` | Public | List notices with search, status, category, ID, date, ordering, pagination, and caching. |
| `POST` | `/api/v1/notices/` | Authenticated user | Create a notice. |
| `GET` | `/api/v1/notices/<slug>/` | Public | Retrieve a notice. |
| `PUT`, `DELETE` | `/api/v1/notices/<slug>/` | Authenticated user | Modify or delete a notice. |

Notices support draft/published status, administrative/academic/events categories, descriptions, images, and generated slugs.

### Certificates and templates

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/certificates/` | Public | List certificates with event-title search. |
| `POST` | `/api/v1/certificates/` | Authenticated user | Create a certificate. |
| `GET` | `/api/v1/certificates/<certificate_id>/` | Public | Retrieve a certificate by UUID. |
| `PUT`, `DELETE` | `/api/v1/certificates/<certificate_id>/` | Authenticated user | Modify or delete a certificate. |
| `GET`, `POST` | `/api/v1/certificates/templates/` | CMS user or admin | List or upload certificate templates. |
| `GET`, `PUT`, `DELETE` | `/api/v1/certificates/templates/<pk>/` | CMS user or admin | Manage one certificate template. |

Certificates contain a generated UUID, full name, event, issue timestamp, and project-completion state. Templates contain a name and uploaded file.

### Past papers

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/past-papers/` | Public | List papers with pagination, caching, and model filters. |
| `POST` | `/api/v1/past-papers/` | Authenticated user | Create a paper. |
| `GET` | `/api/v1/past-papers/<slug>/` | Public | Retrieve a paper with caching. |
| `PUT`, `DELETE` | `/api/v1/past-papers/<slug>/` | Authenticated user | Modify or delete a paper. |

Past papers contain a subject, semester, model-set flag, exam year, optional Drive link, and generated slug. The model enforces uniqueness for subject, semester, and exam year.

### Tenures, members, memberships, and alumni

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/tenures/` | Public | List tenures with nested memberships and caching. |
| `POST` | `/api/v1/tenures/` | Authenticated user | Create a tenure. |
| `GET` | `/api/v1/tenures/<slug>/` | Public | Retrieve a tenure with caching. |
| `PUT`, `DELETE` | `/api/v1/tenures/<slug>/` | Authenticated user | Modify or delete a tenure. |
| `GET` | `/api/v1/members/` | Public | List members. |
| `POST` | `/api/v1/members/` | Authenticated user | Create a member. |
| `GET` | `/api/v1/members/<slug>/` | Public | Retrieve a member with caching. |
| `PUT`, `DELETE` | `/api/v1/members/<slug>/` | Authenticated user | Modify or delete a member. |
| `POST` | `/api/v1/clone-members/<target-tenure-slug>/` | CMS user or admin | Clone members from a source tenure. |
| `GET` | `/api/v1/memberships/` | Public | List tenure memberships. |
| `POST` | `/api/v1/memberships/` | Authenticated user | Create a tenure membership. |
| `GET` | `/api/v1/memberships/<pk>/` | Public | Retrieve a membership. |
| `PUT`, `DELETE` | `/api/v1/memberships/<pk>/` | Authenticated user | Modify or delete a membership. |
| `GET` | `/api/v1/alumni/` | Public | List alumni with pagination and caching. |
| `POST` | `/api/v1/alumni/` | Authenticated user | Create an alumni record. |
| `GET` | `/api/v1/alumni/<pk>/` | Public | Retrieve an alumni record. |
| `PUT`, `DELETE` | `/api/v1/alumni/<pk>/` | Authenticated user | Modify or delete an alumni record. |

The clone request body must include the source tenure slug:

```json
{
  "source_tenure_slug": "previous-tenure"
}
```

## Models

- `User`: custom Django user with role and optional profile picture.
- `Event`: event information, status, category, tags, location, capacity, registration details, image, tenure, and mentors.
- `Mentor`: mentor contact, expertise, LinkedIn, photo, and optional member relationship.
- `Notice`: title, description, image, status, category, and slug.
- `Certificate`: UUID, recipient name, event, issue time, and project-completion state.
- `CertificateTemplate`: template name and uploaded file.
- `PastPaper`: subject, semester, model-set flag, exam year, Drive link, and slug.
- `Tenure`: committee name, dates, slug, and president signature.
- `Member`: member contact details, image, social links, and slug.
- `TenureMembership`: member-tenure relationship, role type, designation, and hierarchy order.
- `Alumni`: member profile, related tenures, graduation year, and biography.
- `TimeStampModel`: shared `created_at` and `updated_at` fields inherited by domain models.

## Media, static files, and logging

Development stores uploaded files below `media/` using the local filesystem. Depending on the model, files are stored under paths such as:

- `media/events_templates/`
- `media/mentors_photos/`
- `media/notices/`
- `media/certificate_templates/`
- `media/member_images/`
- `media/profile_pictures/`
- `media/tenure_signatures/`

`MEDIA_URL` is `/media/`. When `USE_CLOUDINARY=true`, development or production settings use Cloudinary storage instead.

Static files use `/static/`, with `staticfiles/` as the production collection directory and WhiteNoise configured as the static-file backend. The repository does not contain a separate frontend build or tracked static asset bundle.

Local logging writes to `logs/` with separate Django, error, security, certificate, paper, event, notice, and tenure log files. When `RENDER=true`, logging switches to console output.

## Testing and operations

Every domain app has a `tests.py` module, but the current test classes are placeholder scaffolds and do not provide endpoint coverage. Useful checks include:

```bash
python manage.py check
python manage.py test
python manage.py makemigrations
python manage.py migrate
```

The project provides both `config.wsgi:application` and `config.asgi:application`. Gunicorn is included as a dependency, but the repository does not include a Procfile, Dockerfile, CI workflow, or Render deployment manifest. Deployment must provide the process command and environment variables.

Production settings require `DJANGO_SECRET_KEY` and `DATABASE_URL`, default to `DEBUG=False`, enable SSL redirect, and mark session and CSRF cookies as secure. Configure `ALLOWED_HOSTS`, Cloudinary credentials when used, and a production database through the deployment environment.

## Administration

Create an administrator with:

```bash
python manage.py createsuperuser
```

Then open `/admin/` to manage users, events, mentors, notices, certificates, certificate templates, past papers, tenures, members, memberships, and alumni.

## Current limitations

- Automated endpoint and model coverage is not yet implemented in the placeholder test modules.
- The email-test and forgot-password API routes are currently disabled.
- Media persistence in production depends on the configured filesystem or Cloudinary deployment setup.
- The repository does not define a frontend application; the root page is a server-rendered API dashboard template.
