# CSITABMC CMS Backend — Comprehensive Architecture & Security Audit Report

**Project**: CSIT Student Association Dashboard (CSITABMC CMS)  
**Framework**: Django 5.2+ / Django REST Framework 3.15+ / SimpleJWT  
**Audit Type**: Read-Only Architecture, Authorization, API Security, and System Configuration Audit  
**Date of Audit**: November 2026  
**Auditor**: Senior Backend Architect & Security Auditor  
**Report File**: `cms-dashbaord/BACKEND_AUDIT_REPORT.md`  

---
thik xa vai sab thik xa
## 1. Executive Summary

This comprehensive audit was conducted across the entire backend codebase of the CSITABMC Content Management System (`cms-dashbaord`). The system powers the administrative operations of the CSIT Association of BMC, managing users, organization tenures, members, alumni, events, mentors, notices, academic past papers, certificates, and editorial blogs.

### Key Audit Metrics
- **Total Backend Applications**: 8 discovered apps (`users`, `core`, `tenure`, `events`, `notices`, `certificates`, `papers`, `blogs`).
- **Total Database Models**: 13 concrete models inspected.
- **Total API Endpoints**: 22 top-level route patterns inspected (covering 45+ distinct HTTP method handlers).
- **Authentication System**: Cookie-based JSON Web Token (JWT) using `djangorestframework-simplejwt` with automated token rotation, blacklisting, and a 30-day absolute session lifetime cap.
- **Role Hierarchy**: 3 recognized user roles (`superadmin`, `admin`, `cms_user`), alongside Django's native `is_superuser` and `is_staff` flags.

### Critical Audit Findings
1. **Pervasive RBAC Bypass on Mutation Endpoints (CRITICAL)**:
   In `apps/tenure` (Tenures, Members, Memberships, Alumni), `apps/notices`, `apps/certificates`, and `apps/papers`, views are configured with `permission_classes = [IsAuthenticatedOrReadOnly]`. While `IsCMSUser` and `IsAdmin` are imported, they are **not connected** to `post`, `put`, or `patch` handlers. Consequently, **any authenticated user with a valid access token** (regardless of whether they are a regular student member, unprivileged account, or staff) can create, update, or mutate notices, members, tenures, past papers, and certificates.
2. **Unrestricted Member Deletion (CRITICAL)**:
   In `apps/tenure/views.py` (`MemberDetailView.delete`, line 209), the delete handler completely lacks permission checks. Unlike notices or events (which verify admin status), **any authenticated user can permanently delete any organization member record**.
3. **Hardcoded Fallback Credentials in Source Code (HIGH)**:
   In `config/settings/development.py` (lines 80–81), fallback SMTP credentials (`EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD`) are committed directly to version control.
4. **Broken Password Reset Pipeline (HIGH)**:
   `ForgotPasswordView` is commented out in `apps/users/urls.py` (lines 12–13), and `ResetPasswordView` explicitly requires `IsAdmin` permission (`permission_classes = [IsAdmin]`). As a result, non-admin users cannot initiate self-service password recovery, and password resets can only be performed by administrators.
5. **Database Cascade Destruction Risk (MEDIUM-HIGH)**:
   `Event.tenure` uses `on_delete=models.CASCADE`. Deleting a tenure record inadvertently cascades and permanently deletes all associated events, event assignments, and certificates connected to those events.
6. **Missing Production HSTS Security Headers (MEDIUM)**:
   While `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, and `X_FRAME_OPTIONS` are configured in `production.py`, HTTP Strict Transport Security (HSTS) headers (`SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`) are omitted.
7. **Inconsistent Signal Cache Invalidation (MEDIUM)**:
   Signal-driven cache invalidation in `apps/core/apps.py` covers events, notices, and members, but omits `Blog`, `PastPaper`, and `Certificate`, leading to cache staleness when these assets are updated.

---

## 2. Backend Architecture and Application Groups

The backend architecture follows a modular Django pattern with shared utilities centralized in `apps/core`. Applications are categorized into logical business domains:

```
cms-dashbaord/
├── config/
│   ├── settings/
│   │   ├── base.py           # Shared settings, SimpleJWT, Logging, REST_FRAMEWORK
│   │   ├── development.py    # SQLite, local media, debug config
│   │   └── production.py     # PostgreSQL, Cloudinary, SSL, security headers
│   ├── urls.py               # Root URL configuration (mounts all v1 APIs)
│   ├── wsgi.py / asgi.py     # Deployment entrypoints
├── apps/
│   ├── core/                 # Shared permissions, pagination, caching, dashboard metrics
│   ├── users/                # Auth, Cookie JWT, user/admin management, token rotation
│   ├── tenure/               # Tenures, committee members, memberships, alumni
│   ├── events/               # Events, mentors, event-mentor assignments
│   ├── notices/              # Announcements, categories, attachments
│   ├── certificates/         # Issue certificates, templates, bulk status
│   ├── papers/               # Past papers repository, semester/subject tracking
│   └── blogs/                # Blog management, slug generation, media upload
├── logs/                     # Local file-based log outputs
└── requirements.txt          # Production dependencies
```

### Application Domain Breakdown

| Application | Domain Group | Responsibilities | Key Models |
|---|---|---|---|
| `apps.core` | System & Infrastructure | Base timestamp model, shared permissions, pagination, versioned caching decorator, dashboard statistics. | `TimeStampModel` (Abstract) |
| `apps.users` | Identity & Access Control | Custom user model, cookie JWT authentication, token rotation, user provisioning, password management. | `User` |
| `apps.tenure` | Organizational Structure | Committee tenure tracking, executive/advisor memberships, member profiles, alumni directory. | `Tenure`, `Member`, `TenureMembership`, `Alumni` |
| `apps.events` | Activities & Mentorship | Event scheduling, ticketing, categorisation, mentor directory, event-mentor role assignments. | `Event`, `Mentor`, `EventMentorAssignment` |
| `apps.notices` | Communications | Official administrative and academic announcements, attachments, status workflows. | `Notice` |
| `apps.certificates` | Document Issuance | Certificate generation, UUID verification identifiers, template file storage, bulk verification. | `Certificate`, `CertificateTemplate` |
| `apps.papers` | Academic Resources | Semester-wise past question papers, subject choices, model sets, curriculum tracking. | `PastPaper` |
| `apps.blogs` | Editorial CMS | Blog articles, automated slug generation with numeric collision resolution, featured images, rich-text media uploads. | `Blog` |

---

## 3. Authentication System Audit

### 3.1 Authentication Mechanisms
The primary authentication scheme is implemented in `apps.users.authentication.CookieJWTAuthentication` (inheriting from `rest_framework_simplejwt.authentication.JWTAuthentication`).

- **Cookie Extraction**: Inspects incoming HTTP requests for an `access_token` cookie (`request.COOKIES.get("access_token")`).
- **Authorization Header Fallback**: If the cookie is absent, it falls back to standard HTTP `Authorization: Bearer <token>` header inspection.
- **Fail-Safe Behavior**: If a token is expired or invalid, it returns `None` rather than raising an exception, allowing anonymous access to public endpoints while denying access to protected ones.

### 3.2 Token Lifecycle & Session Policies (`config/settings/base.py` & `apps/users/views.py`)
- **Access Token Lifetime**: 1 hour (`ACCESS_TOKEN_LIFETIME = timedelta(hours=1)`).
- **Refresh Token Lifetime**: 7 days (`REFRESH_TOKEN_LIFETIME = timedelta(days=7)`).
- **Token Rotation**: `ROTATE_REFRESH_TOKENS = True`. On each call to `/api/v1/users/refresh-token/`, a new refresh token is issued.
- **Blacklisting**: `BLACKLIST_AFTER_ROTATION = True`. The replaced refresh token is immediately blacklisted in the database (`OutstandingToken` / `BlacklistedToken`).
- **Absolute Session Lifetime Cap**: `JWT_SESSION_MAX_LIFETIME = timedelta(days=30)`. When the user initially logs in, a custom claim `session_start` is injected into the refresh token. Every rotation checks `now.timestamp() >= session_end`. If the session exceeds 30 days from initial login, the token is blacklisted, cookies are wiped, and re-login is required.
- **Cookie Security Flags**:
  - `httponly = True` (inaccessible to JavaScript).
  - `secure = True` in production (`not settings.DEBUG`).
  - `samesite = "None"` in production (allows cross-site requests with credentials), `"Lax"` in development.

### 3.3 Authentication Endpoints

| Endpoint | Method | Permission | Throttling | Audit Notes |
|---|---|---|---|---|
| `/api/v1/login/` | `POST` | `AllowAny` | `AnonRateThrottle` | Verifies email and password. Issues `access_token` and `refresh_token` in cookies. Returns user object with role. |
| `/api/v1/users/refresh-token/` | `POST` | `AllowAny` | None | Rotates refresh token, blacklists old token, enforces 30-day session cap. Wipes cookies on failure. |
| `/api/v1/users/logout/` | `POST` | `IsAuthenticated` | None | Reads refresh token from cookie, blacklists token, clears cookies via `_clear_session_cookies`. |
| `/api/v1/users/change-password/` | `POST` | `[IsAuthenticated, IsCMSUser]` | `UserRateThrottle` | Validates `old_password`, updates to `new_password` via `set_password`. |
| `/api/v1/users/reset-password/` | `POST` | `[IsAdmin]` | `UserRateThrottle` | Decodes base64 `uid`, validates Django `default_token_generator` token, resets password. **Restricted to Admin only**. |
| `/api/v1/users/forgot-password/` | `POST` | *Commented Out* | N/A | **Disabled in `urls.py`**. Cannot be reached. |

### 3.4 Authentication Gaps & Weaknesses
1. **No Brute-Force Protection on Login Beyond Daily Limit**:
   `AnonRateThrottle` is set to `100/day`. There is no per-minute or per-hour rate limiting (e.g., `5/minute`), allowing rapid bursts of failed login attempts before reaching the daily ceiling.
2. **No Email Verification / Account Activation**:
   Newly created accounts are immediately marked `is_active=True`. There is no email verification flow.
3. **No Self-Service Password Recovery**:
   Because `forgot-password/` is commented out and `reset-password/` requires `IsAdmin`, a standard user who forgets their password has no automated recovery path.

---

## 4. Roles and Permission System Audit

### 4.1 Defined Roles
User roles are declared in `apps.users.models.User.ROLE_CHOICES`:
1. **`superadmin`**: Unrestricted platform owner. Automatically inherits all permissions.
2. **`admin`**: System administrator. Allowed to manage CMS users, manage content, and delete assets. Cannot modify peer admins or superadmins.
3. **`cms_user`**: Content editor / association representative. Intended to create and edit content (events, notices, members, blogs), but prohibited from administrative user management and deletions.

*Note: Roles such as "Executive", "Advisor", or "General Member" do NOT exist on the User account model; they exist only as categorical designations in `TenureMembership.RoleType`.*

### 4.2 Custom Permission Classes (`apps/core/permission.py`)

#### `IsAdmin`
```python
class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and (
                request.user.role in ['admin', 'superadmin']
                or request.user.is_superuser
            )
        )
```
- **Evaluation**: Enforces that the user is authenticated and possesses either `admin`, `superadmin`, or `is_superuser`.
- **Limitation**: Implements `has_permission` only. Does NOT implement `has_object_permission`.

#### `IsCMSUser`
```python
class IsCMSUser(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and (
                request.user.role in ['admin', 'superadmin', 'cms_user']
                or request.user.is_superuser
            )
        )
```
- **Evaluation**: Permits all administrative and CMS editor roles. Denies unauthenticated or foreign roles.
- **Limitation**: Implements `has_permission` only. Does NOT implement `has_object_permission`.

### 4.3 Permission Architecture Flaws
- **Disconnection in Core Modules**: In `apps/notices`, `apps/tenure`, `apps/certificates`, and `apps/papers`, the view classes declare `permission_classes = [IsAuthenticatedOrReadOnly]`. While `IsCMSUser` is imported at the top of these files, it is **never assigned** to `permission_classes` or checked inside `post()` or `put()` methods.
- **Result**: Any user who acquires a valid JWT (even an account with an unrecognized role or a member role) can perform full create and update actions across Notices, Members, Tenures, Certificates, and Past Papers.
- **Absence of Object-Level Permissions**: There is no concept of resource ownership. Any editor can modify or overwrite any other editor's drafted notice, event, or article.

---

## 5. Role and Permission Matrix

The following matrix documents the **actual enforced backend permissions** vs **expected design permissions** across all system actions.

| Module | Action | Superadmin | Admin | CMS User | Authenticated Non-Admin | Anonymous (Public) | Actual Enforcement Level |
|---|---|---|---|---|---|---|---|
| **Auth** | Login (`/login/`) | Allowed | Allowed | Allowed | Allowed | Allowed | `AllowAny` |
| **Auth** | Refresh Token (`/refresh-token/`) | Allowed | Allowed | Allowed | Allowed | Allowed | `AllowAny` (Validates refresh cookie) |
| **Auth** | Logout (`/logout/`) | Allowed | Allowed | Allowed | Allowed | Denied | `IsAuthenticated` |
| **Auth** | Change Password | Allowed | Allowed | Allowed | Denied (if not CMS) | Denied | `[IsAuthenticated, IsCMSUser]` |
| **Users** | List Users (`GET /users/`) | Allowed | Allowed | Denied | Denied | Denied | `IsAdmin` |
| **Users** | Create User (`POST /users/`) | Allowed | Allowed (CMS only) | Denied | Denied | Denied | `IsAdmin` (View checks `is_superadmin` for admin roles) |
| **Users** | Update User (`PUT/PATCH /users/<id>/`) | Allowed | Allowed (Peer restricted) | Denied | Denied | Denied | `IsAdmin` (View blocks peer/superior edits) |
| **Users** | Delete User (`DELETE /users/<id>/`) | Allowed | Allowed (Peer restricted) | Denied | Denied | Denied | `IsAdmin` (View blocks self & peer deletes) |
| **Dashboard** | Stats (`GET /dashboard/stats/`) | Allowed | Allowed | Allowed | Allowed | **Allowed** | `IsAuthenticatedOrReadOnly` (Public read) |
| **Tenure** | List/Retrieve Tenures | Allowed | Allowed | Allowed | Allowed | Allowed | `IsAuthenticatedOrReadOnly` (Cached) |
| **Tenure** | Create Tenure (`POST /tenures/`) | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Tenure** | Update Tenure (`PUT /tenures/<slug>/`) | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Tenure** | Delete Tenure (`DELETE /tenures/<slug>/`) | Allowed | Allowed | Denied | Denied | Denied | In-method check (`IsAdmin or is_staff`) |
| **Members** | List/Retrieve Members | Allowed | Allowed | Allowed | Allowed | Allowed | `IsAuthenticatedOrReadOnly` |
| **Members** | Create Member (`POST /members/`) | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Members** | Update Member (`PUT/PATCH /members/<slug>/`) | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Members** | Delete Member (`DELETE /members/<slug>/`) | Allowed | Allowed | **Allowed (CRITICAL)** | **Allowed (CRITICAL)** | Denied | **No check in method! Anyone authenticated can delete** |
| **Memberships** | Create/Update Membership | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Memberships** | Delete Membership | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Memberships** | Clone Memberships (`POST /clone-members/`) | Allowed | Allowed | Allowed | Denied | Denied | `@permission_classes([IsCMSUser])` |
| **Alumni** | Create/Update Alumni | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Alumni** | Delete Alumni | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Events** | List/Retrieve Events | Allowed | Allowed | Allowed | Allowed | Allowed | `get_permissions` (`AllowAny`) |
| **Events** | Create/Update Events | Allowed | Allowed | Allowed | Denied | Denied | `get_permissions` (`IsCMSUser`) |
| **Events** | Delete Event (`DELETE /events/<slug>/`) | Allowed | Allowed | Denied | Denied | Denied | In-method check (`IsAdmin or is_staff`) |
| **Mentors** | List/Retrieve Mentors | Allowed | Allowed | Allowed | Allowed | Allowed | `get_permissions` (`AllowAny`) |
| **Mentors** | Create/Update Mentors | Allowed | Allowed | Allowed | Denied | Denied | `get_permissions` (`IsCMSUser`) |
| **Mentors** | Delete Mentor (`DELETE /mentors/<id>/`) | Allowed | Allowed | Denied | Denied | Denied | In-method check (`IsAdmin or is_staff`) |
| **Notices** | List/Retrieve Notices | Allowed | Allowed | Allowed | Allowed | Allowed | `IsAuthenticatedOrReadOnly` (Cached) |
| **Notices** | Create Notice (`POST /notices/`) | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Notices** | Update Notice (`PUT /notices/<slug>/`) | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Notices** | Delete Notice (`DELETE /notices/<slug>/`) | Allowed | Allowed | Denied | Denied | Denied | In-method check (`IsAdmin or is_staff`) |
| **Certificates** | List/Retrieve Certificates | Allowed | Allowed | Allowed | Allowed | Allowed | `IsAuthenticatedOrReadOnly` |
| **Certificates** | Issue Certificate (`POST /certificates/`) | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Certificates** | Update Certificate (`PUT /certificates/<uuid>/`) | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Certificates** | Bulk Status Update (`PATCH /certificates/`) | Allowed | Allowed | Allowed | Denied | Denied | In-method check (`role in ('admin', 'cms_user')`) |
| **Certificates** | Delete Certificate (`DELETE /certificates/<uuid>/`) | Allowed | Allowed | Denied | Denied | Denied | In-method check (`IsAdmin or is_staff`) |
| **Cert Templates** | Create/Update/Delete Template | Allowed | Allowed | Allowed | Denied | Denied | `IsCMSUser` |
| **Past Papers** | List/Retrieve Past Papers | Allowed | Allowed | Allowed | Allowed | Allowed | `IsAuthenticatedOrReadOnly` |
| **Past Papers** | Create Past Paper (`POST /past-papers/`) | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Past Papers** | Update Past Paper (`PUT /past-papers/<slug>/`) | Allowed | Allowed | Allowed | **Allowed (GAP)** | Denied | `IsAuthenticatedOrReadOnly` |
| **Past Papers** | Delete Past Paper (`DELETE /past-papers/<slug>/`) | Allowed | Allowed | Denied | Denied | Denied | In-method check (`IsAdmin or is_staff`) |
| **Blogs** | List/Retrieve Blogs | Allowed | Allowed | Allowed | Allowed | Allowed | `get_permissions` (`IsAuthenticatedOrReadOnly`) |
| **Blogs** | Create/Update Blog | Allowed | Allowed | Allowed | Denied | Denied | `get_permissions` (`[IsAuthenticated, IsCMSUser]`) |
| **Blogs** | Delete Blog (`DELETE /blogs/<id>/`) | Allowed | Allowed | Denied | Denied | Denied | In-method check (`IsAdmin or is_staff`) |
| **Blogs** | Upload Content Image (`POST /blogs/upload-image/`) | Allowed | Allowed | Allowed | Denied | Denied | `permission_classes = [IsAuthenticated, IsCMSUser]` |

---

## 6. User and Admin Management Audit

### 6.1 Custom User Model (`apps/users/models.py`)
```python
class User(AbstractUser):
    ROLE_CHOICES = (
        ('superadmin', 'Superadmin'),
        ('admin', 'Admin'),
        ('cms_user', 'Cms User')
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cms_user')
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
```
- **Strengths**: Extends `AbstractUser` cleanly. Passwords use standard Django PBKDF2 hashing.
- **Weaknesses**:
  - `role` is un-indexed (`db_index=False`).
  - No `is_active` transition tracking or deactivation audit logging.
  - No soft-deletion flag (e.g. `is_deleted`). Accounts are permanently destroyed via raw `user.delete()`.

### 6.2 Administrative Account Hierarchy Controls (`apps/users/views.py`)
The backend has explicit security checks in `UserView` and `UserDetailView`:
1. **Admin Promotion Protection**:
   `UserView.post` (lines 201–209) and `UserDetailView.put/patch` (lines 131–137, 160–166) check:
   ```python
   if target_role in ['admin', 'superadmin'] and not is_superadmin(request.user):
       return Response({"detail": "Only superadmins can create/assign administrative accounts."}, status=403)
   ```
   *An admin cannot escalate their own privileges or create peer admins.*
2. **Peer Modification Protection**:
   In `UserDetailView` (lines 122–130), an admin attempting to modify another user with `role in ['admin', 'superadmin']` or `is_superuser` is rejected with HTTP 403 Forbidden.
3. **Self-Deletion Protection**:
   In `UserDetailView.delete` (line 178), `if str(request.user.id) == str(user_id)` returns HTTP 400 Bad Request to prevent admins from locking themselves out.

### 6.3 Missing Account Lifecycle Features
- **Profile Self-Management Endpoint**: There is no `/api/v1/users/me/` or `/api/v1/profile/` endpoint allowing a logged-in `cms_user` to update their own avatar or display name.
- **Audit Logging of Privileged Changes**: Role changes are logged to file logger `security`, but there is no persistent audit table in the database recording who changed which user's permissions.

---

## 7. Module-by-Module API Inventory

| Module | Endpoint URL | Allowed Methods | Authentication | Permission Enforcement | Caching | Status |
|---|---|---|---|---|---|---|
| **Users** | `/api/v1/login/` | `POST` | None | `AllowAny` | None | Fully Implemented |
| **Users** | `/api/v1/users/refresh-token/` | `POST` | Cookie (Refresh) | `AllowAny` | None | Fully Implemented |
| **Users** | `/api/v1/users/logout/` | `POST` | Cookie / Header | `IsAuthenticated` | None | Fully Implemented |
| **Users** | `/api/v1/users/` | `GET`, `POST` | Cookie / Header | `IsAdmin` | None | Fully Implemented |
| **Users** | `/api/v1/users/<id>/` | `GET`, `PUT`, `PATCH`, `DELETE` | Cookie / Header | `IsAdmin` + Peer Checks | None | Fully Implemented |
| **Users** | `/api/v1/users/change-password/` | `POST` | Cookie / Header | `[IsAuthenticated, IsCMSUser]` | None | Fully Implemented |
| **Users** | `/api/v1/users/reset-password/` | `POST` | Cookie / Header | `IsAdmin` (Incomplete flow) | None | Partially Implemented |
| **Core** | `/api/v1/dashboard/stats/` | `GET` | Optional | `IsAuthenticatedOrReadOnly` | None | Fully Implemented |
| **Tenure** | `/api/v1/tenures/` | `GET`, `POST` | Optional (GET) | `IsAuthenticatedOrReadOnly` | 5 min versioned | Partially Protected |
| **Tenure** | `/api/v1/tenures/<slug>/` | `GET`, `PUT`, `DELETE` | Optional (GET) | `IsAuthenticatedOrReadOnly` (Del: Admin) | 5 min versioned | Partially Protected |
| **Tenure** | `/api/v1/members/` | `GET`, `POST` | Optional (GET) | `IsAuthenticatedOrReadOnly` | None | Partially Protected |
| **Tenure** | `/api/v1/members/<slug>/` | `GET`, `PUT`, `PATCH`, `DELETE` | Optional (GET) | `IsAuthenticatedOrReadOnly` (**Del: None**) | 5 min versioned | **Vulnerable** |
| **Tenure** | `/api/v1/memberships/` | `GET`, `POST` | Optional (GET) | `IsAuthenticatedOrReadOnly` | None | Partially Protected |
| **Tenure** | `/api/v1/memberships/<id>/` | `GET`, `PUT`, `DELETE` | Optional (GET) | `IsAuthenticatedOrReadOnly` | None | Partially Protected |
| **Tenure** | `/api/v1/clone-members/<slug>/` | `POST` | Required | `IsCMSUser` | Clears cache | Fully Implemented |
| **Tenure** | `/api/v1/alumni/` | `GET`, `POST` | Optional (GET) | `IsAuthenticatedOrReadOnly` | 5 min versioned | Partially Protected |
| **Tenure** | `/api/v1/alumni/<id>/` | `GET`, `PUT`, `PATCH`, `DELETE` | Optional (GET) | `IsAuthenticatedOrReadOnly` | None | Partially Protected |
| **Events** | `/api/v1/events/` | `GET`, `POST` | Optional (GET) | GET: `AllowAny`, POST: `IsCMSUser` | 5 min versioned | Fully Implemented |
| **Events** | `/api/v1/events/<slug>/` | `GET`, `PUT`, `PATCH`, `DELETE` | Optional (GET) | GET: `AllowAny`, Mut: `IsCMSUser`, Del: Admin | 5 min versioned | Fully Implemented |
| **Events** | `/api/v1/mentors/` | `GET`, `POST` | Optional (GET) | GET: `AllowAny`, POST: `IsCMSUser` | 5 min versioned | Fully Implemented |
| **Events** | `/api/v1/mentors/<id>/` | `GET`, `PUT`, `PATCH`, `DELETE` | Optional (GET) | GET: `AllowAny`, Mut: `IsCMSUser`, Del: Admin | 5 min versioned | Fully Implemented |
| **Notices** | `/api/v1/notices/` | `GET`, `POST` | Optional (GET) | `IsAuthenticatedOrReadOnly` | 5 min versioned | Partially Protected |
| **Notices** | `/api/v1/notices/<slug>/` | `GET`, `PUT`, `DELETE` | Optional (GET) | `IsAuthenticatedOrReadOnly` (Del: Admin) | 5 min versioned | Partially Protected |
| **Certificates** | `/api/v1/certificates/templates/` | `GET`, `POST` | Required | `IsCMSUser` | None | Fully Implemented |
| **Certificates** | `/api/v1/certificates/templates/<id>/` | `GET`, `PUT`, `DELETE` | Required | `IsCMSUser` | None | Fully Implemented |
| **Certificates** | `/api/v1/certificates/` | `GET`, `POST`, `PATCH` | Optional (GET) | GET/POST: `IsAuthOrReadOnly`, PATCH: `role` check | None | Partially Protected |
| **Certificates** | `/api/v1/certificates/<uuid>/` | `GET`, `PUT`, `DELETE` | Optional (GET) | `IsAuthenticatedOrReadOnly` (Del: Admin) | None | Partially Protected |
| **Papers** | `/api/v1/past-papers/` | `GET`, `POST` | Optional (GET) | `IsAuthenticatedOrReadOnly` | None | Partially Protected |
| **Papers** | `/api/v1/past-papers/<slug>/` | `GET`, `PUT`, `DELETE` | Optional (GET) | `IsAuthenticatedOrReadOnly` (Del: Admin) | None | Partially Protected |
| **Blogs** | `/api/v1/blogs/` | `GET`, `POST` | Optional (GET) | GET: `AllowAny`, POST: `[Auth, IsCMSUser]` | None | Fully Implemented |
| **Blogs** | `/api/v1/blogs/<id_or_slug>/` | `GET`, `PUT`, `PATCH`, `DELETE` | Optional (GET) | GET: `AllowAny`, Mut: `IsCMSUser`, Del: Admin | None | Fully Implemented |
| **Blogs** | `/api/v1/blogs/upload-image/` | `POST` | Required | `[IsAuthenticated, IsCMSUser]` | None | Fully Implemented |

---

## 8. Database and Data Integrity Audit

### 8.1 Model Relationships and Integrity Checks
- **`TenureMembership`**:
  - `member = ForeignKey(Member, on_delete=CASCADE)`
  - `tenure = ForeignKey(Tenure, on_delete=CASCADE)`
  - `unique_together = ('member', 'tenure')`
  - **Verdict**: Excellent. Prevents assigning the same member to the same tenure twice.
- **`EventMentorAssignment`**:
  - `event = ForeignKey(Event, on_delete=CASCADE)`
  - `mentor = ForeignKey(Mentor, on_delete=CASCADE)`
  - `unique_together = ('event', 'mentor')`
  - **Verdict**: Excellent. Clean join table with customizable roles and responsibilities.
- **`Alumni`**:
  - `member = OneToOneField(Member, on_delete=CASCADE)`
  - `tenures = ManyToManyField(Tenure, related_name='alumni')`
  - **Verdict**: Solid one-to-one mapping ensuring a member can only have one alumni dossier.
- **`Certificate`**:
  - `certificate_id = UUIDField(default=uuid.uuid4, editable=False, unique=True)`
  - `event = ForeignKey(Event, on_delete=CASCADE)`
  - **Integrity Risk**: If an `Event` is deleted, all issued certificates for that event are cascaded and deleted! Certificate records should generally outlive events. Recommended: `on_delete=models.PROTECT` or `on_delete=models.SET_NULL`.
- **`Event.tenure`**:
  - `tenure = ForeignKey(Tenure, on_delete=CASCADE, null=True, blank=True)`
  - **Integrity Risk**: Deleting a committee `Tenure` cascades and destroys all historical events produced during that tenure. Recommended: `on_delete=models.SET_NULL` or `on_delete=models.PROTECT`.
- **`PastPaper`**:
  - `unique_together = ('subject_name', 'semester', 'exam_year', 'model_set', 'is_old_course')`
  - **Verdict**: Highly accurate constraint preventing duplicate exam uploads for the same year and set.

### 8.2 Slug Generation and Collision Safety
- **`Notice` & `Blog`**: Feature atomic transaction retry loops (`transaction.atomic()` catching `IntegrityError`) and sequential suffix incrementing (`-2`, `-3`). This ensures high-concurrency safety.
- **`Tenure` & `Member` & `Event`**: Implement standard while-loop checks (`while Model.objects.filter(slug=candidate).exists(): counter += 1`), but lack the atomic retry block. Under extreme concurrent creation with identical names, an unhandled `IntegrityError` could theoretically be raised.

---

## 9. Security Configuration Audit

### 9.1 Core Django Settings
- **`DEBUG` Flag**:
  - `development.py`: `DEBUG = True` (Appropriate).
  - `production.py`: `DEBUG = False` (Appropriate).
- **`SECRET_KEY`**:
  - `production.py`: `SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")`.
  - In `development.py`: Hardcoded fallback string `"django-insecure-dev-only-key-change-me"` is present, which is standard for local setups.
- **Allowed Hosts**:
  - `production.py`: Derived from `ALLOWED_HOSTS` environment variable with fallback to `"cms.csitabmc.com"`.
- **CORS & CSRF**:
  - `corsheaders.middleware.CorsMiddleware` is correctly placed at the very top of `MIDDLEWARE`.
  - `CORS_ALLOW_CREDENTIALS = True` (Required for cookie JWT transport).
  - `CSRF_TRUSTED_ORIGINS` includes `http://localhost:3000` and `https://cms.csitabmc.com`.

### 9.2 HTTPS, Cookies, and Transport Security
- **Production Cookie Settings (`production.py`)**:
  - `SECURE_SSL_REDIRECT = True` (Forces HTTPS redirect).
  - `SESSION_COOKIE_SECURE = True`.
  - `CSRF_COOKIE_SECURE = True`.
  - `X_FRAME_OPTIONS = "DENY"` (Protects against clickjacking).
  - `SECURE_BROWSER_XSS_FILTER = True`.
  - `SECURE_CONTENT_TYPE_NOSNIFF = True`.
- **Missing Production Transport Controls**:
  - `SECURE_HSTS_SECONDS` is **not configured** (Recommended: 31536000 / 1 year).
  - `SECURE_HSTS_INCLUDE_SUBDOMAINS` is **not configured**.
  - `SECURE_HSTS_PRELOAD` is **not configured**.
  - `Content-Security-Policy` (CSP) header is not configured.

### 9.3 File and Media Security
- **Secure File Naming**:
  All models (`Notice.image`, `Event.image`, `Mentor.photo`, `Member.image`, `Tenure.signature`, `Blog.featured_image`) utilize `SecureFilePath` which generates random UUID4 filenames:
  ```python
  ext = os.path.splitext(filename)[1].lower()
  secure_name = f"{uuid.uuid4()}{ext}"
  ```
  *This effectively neutralizes directory traversal (`../../`) and prevents filename collision overwrites.*
- **File Size Validation**:
  `validate_file_size` enforces a strict 5MB limit (`5 * 1024 * 1024`) across file fields.
- **Cloudinary Integration**:
  In `production.py` and when `USE_CLOUDINARY=true`, `cloudinary_storage.storage.MediaCloudinaryStorage` is mounted as default storage.
  *Note on `development.py`*: Line 68 defines `STORAGES = { **STORAGES, ... }`. When not executing `test`, `STORAGES` is not initially defined in `base.py`, which will throw a `NameError` if `USE_CLOUDINARY=True` is enabled locally.

---

## 10. Other Backend Configurations

### 10.1 Logging System (`config/settings/base.py`)
- **Render vs Local File Output**: When `RENDER="true"`, logs are piped to stdout (`logging.StreamHandler`). When running locally, logs are persisted to designated log files in `cms-dashbaord/logs/`:
  - `django.log` & `errors.log`: Django core and unhandled 500 exceptions.
  - `security.log`: Authentication attempts, forbidden mutations, password changes.
  - Domain logs: `event.log`, `notice.log`, `tenure.log`, `certificate.log`, `pastpaper.log`.
- **Verdict**: Well-configured and structured.

### 10.2 Response Caching Architecture (`apps/core/cache.py`)
- **Mechanism**: Custom `@versioned_cache_page(timeout)` decorator wrapping Django's standard `cache_page`.
- **Cache Keying**: Prefixes cache keys with a global version integer (`content-v{N}`).
- **Signal Invalidation**: When any registered model is saved or deleted, `apps/core/apps.py` calls `bump_content_cache_version()`, incrementing the version and instantly invalidating all cached responses without requiring cache clearing.
- **Coverage**: Registered for `Event`, `Mentor`, `Notice`, `Tenure`, `Member`, `TenureMembership`, `Alumni`.
- **Omissions**: `Blog`, `PastPaper`, and `Certificate` are not registered with the signal receiver.

### 10.3 Background Tasks & Asynchronous Workers
- **Celery / Redis / RQ**: None detected. All operations (including database transactions, media uploads, and bulk operations) execute synchronously within the WSGI/ASGI request cycle.

---

## 11. Missing and Incomplete Functionality

### Category A: Critical Security Deficiencies
1. **Unenforced RBAC on Notices, Tenures, Members, Certificates, and Past Papers**:
   - `apps/notices/views.py`: `NoticeListView.post` and `NoticeDetailView.put` allow any authenticated token holder to write.
   - `apps/tenure/views.py`: `TenureListView.post`, `TenureDetailView.put`, `MemberListView.post`, `MemberDetailView.put/patch`, `TenureMembershipListView.post`, `TenureMembershipDetailView.put/delete`, `AlumniListView.post`, `AlumniDetailView.put/patch/delete` lack `IsCMSUser` enforcement.
   - `apps/certificates/views.py`: `CertificateListView.post` and `CertificateDetailView.put` lack `IsCMSUser` enforcement.
   - `apps/papers/views.py`: `PastPaperListView.post` and `PastPaperDetailView.put` lack `IsCMSUser` enforcement.
2. **Missing Delete Protection in `MemberDetailView`**:
   - `apps/tenure/views.py` line 209: The `delete` method does not verify that `request.user` is an admin or staff member. Any authenticated user can delete member records.
3. **Committed SMTP Password in `development.py`**:
   - `EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "xvmz fpzx eykp gzop")` exposes a live Gmail application-specific password.

### Category B: Important Operational Deficiencies
1. **Inoperable Self-Service Password Reset**:
   - `forgot-password/` is commented out in `apps/users/urls.py`, and `reset-password/` requires `IsAdmin`. Users cannot recover forgotten passwords without administrator intervention.
2. **Dangerous Database Cascade Rules on Core Entities**:
   - `Event.tenure`: `on_delete=models.CASCADE` deletes all events if a tenure is removed.
   - `Certificate.event`: `on_delete=models.CASCADE` deletes all certificates if an event is removed.
3. **Missing Production HSTS Headers**:
   - Omission of `SECURE_HSTS_SECONDS` leaves users vulnerable to SSL stripping attacks on initial connections.
4. **Lack of Burst Rate Limiting**:
   - DRF rate limiting uses daily buckets (`100/day`, `1000/day`). Bursts of 90 login requests in 10 seconds will pass through.

### Category C: Recommended Improvements
1. **Absence of User Self-Management (`/api/v1/users/me/`)**:
   - Currently, non-admin users cannot fetch or edit their own profile, avatar, or details.
2. **Missing Test Coverage in `apps/certificates`**:
   - `apps/certificates/tests.py` is an empty file (60 bytes) with zero test assertions.
3. **Incomplete Signal Cache Invalidation**:
   - `Blog` and `PastPaper` models are not connected to `bump_content_cache_version`.

### Category D: Optional Enhancements
1. **Asynchronous Task Queue (Celery/Redis)**:
   - For image processing, certificate PDF rendering, or batch emails.
2. **Audit Log Database Model**:
   - Persistent database record of who changed which records, replacing ephemeral log files.

---

## 12. Risk and Priority Assessment

| Finding ID | Severity | Area | Description | Impact |
|---|---|---|---|---|
| **SEC-01** | **CRITICAL** | Authorization | Write methods in `notices`, `tenure`, `certificates`, `papers` lack `IsCMSUser`. | Any user with a valid access token can modify organizational data. |
| **SEC-02** | **CRITICAL** | Authorization | `MemberDetailView.delete` has zero role checks. | Any authenticated user can delete members from the system. |
| **SEC-03** | **HIGH** | Secrets Management | Gmail app password committed to `development.py`. | Credential exposure. |
| **SEC-04** | **HIGH** | Account Lifecycle | `forgot-password` commented out; `reset-password` requires `IsAdmin`. | Broken password recovery workflow. |
| **DAT-01** | **HIGH** | Data Integrity | `CASCADE` on `Event.tenure` and `Certificate.event`. | Deleting a tenure or event destroys all associated certificates and records. |
| **SEC-05** | **MEDIUM** | Security Headers | Missing `SECURE_HSTS_SECONDS` in `production.py`. | Incomplete SSL enforcement against MITM. |
| **SEC-06** | **MEDIUM** | Rate Limiting | No minute-level throttling on login or mutations. | Potential credential stuffing or rapid spamming. |
| **SYS-01** | **MEDIUM** | Caching | `Blog` and `PastPaper` omitted from signal cache invalidation. | Potential stale content delivered to users. |
| **TST-01** | **LOW** | QA & Testing | `apps/certificates/tests.py` has zero test cases. | Regression risk during certificate updates. |

---

## 13. Recommended Permission Structure

To ensure rock-solid, uniform security across the entire CSITABMC backend without breaking existing frontend contracts, the following permissions architecture is recommended for adoption:

### 13.1 Universal View Permission Pattern
Every `APIView` handling public reads and privileged writes should adopt the declarative `get_permissions()` pattern already proven in `apps/events/views.py` and `apps/blogs/views.py`:

```python
class StandardCMSAPIView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_permissions(self):
        if self.request.method in ["GET", "HEAD", "OPTIONS"]:
            return [AllowAny()] # Or IsAuthenticatedOrReadOnly()
        if self.request.method == "DELETE":
            return [IsAdmin()]
        return [IsCMSUser()]
```

### 13.2 Recommended Role Capabilities

```
+--------------------------------------------------------------------------+
|                               SUPERADMIN                                 |
|  - Full access to all endpoints                                          |
|  - Assign Admin and Superadmin roles                                     |
|  - Provision system configurations & database migrations                 |
+------------------------------------+-------------------------------------+
                                     |
+------------------------------------v-------------------------------------+
|                                 ADMIN                                    |
|  - Manage CMS Users (create, update, deactivate)                         |
|  - Delete any Content, Event, Notice, Member, Tenure, Certificate        |
|  - Full create/update across all modules                                 |
|  - Cannot modify peer Admins or promote accounts to Admin/Superadmin     |
+------------------------------------+-------------------------------------+
                                     |
+------------------------------------v-------------------------------------+
|                                CMS USER                                  |
|  - Create & Edit Content (Notices, Events, Blogs, Members, Papers)       |
|  - Issue & update Certificates                                           |
|  - Clone committee members across tenures                                |
|  - CANNOT delete records                                                 |
|  - CANNOT access User Management endpoints                               |
+------------------------------------+-------------------------------------+
                                     |
+------------------------------------v-------------------------------------+
|                         AUTHENTICATED / MEMBER                           |
|  - Read public and authenticated resources                               |
|  - Update own profile (/users/me/) & change own password                 |
|  - CANNOT create, update, or delete any CMS data                         |
+--------------------------------------------------------------------------+
```

---

## 14. Implementation Roadmap

### Phase 1: Immediate Security Hardening (P0 — Urgent)
1. **Fix RBAC Disconnection**:
   - Update `NoticeListView`, `NoticeDetailView` to enforce `IsCMSUser` on POST/PUT and `IsAdmin` on DELETE.
   - Update `MemberListView`, `MemberDetailView`, `TenureListView`, `TenureDetailView`, `TenureMembershipListView`, `TenureMembershipDetailView`, `AlumniListView`, `AlumniDetailView` to enforce `IsCMSUser` on POST/PUT/PATCH and `IsAdmin` on DELETE.
   - Fix `MemberDetailView.delete` immediately by adding `IsAdmin` verification.
   - Update `CertificateListView`, `CertificateDetailView`, `PastPaperListView`, `PastPaperDetailView` to enforce `IsCMSUser` on POST/PUT.
2. **Purge Secrets from Source Code**:
   - Remove hardcoded email password from `development.py` (lines 80–81). Require `EMAIL_HOST_PASSWORD` to be read strictly from `.env`.

### Phase 2: Integrity & Account Lifecycle Fixes (P1 — High Priority)
1. **Protect Relational Integrity**:
   - Change `Event.tenure` from `CASCADE` to `on_delete=models.SET_NULL` or `PROTECT`.
   - Change `Certificate.event` from `CASCADE` to `on_delete=models.PROTECT`.
2. **Restore Password Recovery Pipeline**:
   - Re-enable `forgot-password/` endpoint.
   - Change `ResetPasswordView.permission_classes` from `[IsAdmin]` to `[AllowAny]`, relying on the one-time cryptographic token verification.
3. **Configure HSTS Headers**:
   - Add `SECURE_HSTS_SECONDS = 31536000`, `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`, and `SECURE_HSTS_PRELOAD = True` in `config/settings/production.py`.

### Phase 3: Architecture & Operational Polish (P2 — Medium Priority)
1. **Implement `/api/v1/users/me/`**:
   - Allow logged-in users to view and update their own name, email, and avatar.
2. **Expand Cache Signals**:
   - Add `Blog` and `PastPaper` models to `apps/core/apps.py` cache version bumping signals.
3. **Comprehensive Test Suite**:
   - Write automated permission verification tests for `apps/certificates`, `apps/tenure`, and `apps/notices`.

---

## 15. Audit Limitations and Unverified Areas

1. **Static Analysis & Local Test Environment**:
   This audit was conducted by inspecting source code files, configurations, and running tests against a local development environment. Live production network traffic, DNS records, and cloud deployment firewalls (e.g. Render/Cloudflare WAF) were not probed.
2. **Cloudinary Asset Storage**:
   Cloudinary credentials and storage buckets were inspected in configuration, but external bucket-level access control lists (ACLs) on Cloudinary's management console were not evaluated.
3. **Database Migration State**:
   Existing migrations were inspected. SQLite was used in local testing; PostgreSQL-specific constraints in a live hosted database were verified via Django model definitions.

---

*Report concluded. All findings reflect the exact state of the `cms-dashbaord` repository as of November 2026.*
