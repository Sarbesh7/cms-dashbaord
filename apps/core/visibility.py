"""
Public vs. privileged read access.

Read endpoints stay open for genuinely public, published content. Callers who
hold ``<module>.view`` (dashboard roles) additionally see drafts and private
fields. Authentication alone is not enough: an authenticated user without the
module permission gets exactly the public view.
"""
from apps.core.permissions import user_has_permission

PUBLIC_EVENT_STATUSES = ("published", "completed")
PUBLISHED = "published"


def can_view_private(request, module):
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user_has_permission(user, f"{module}.view"))


def strip_fields(data, fields):
    for field in fields:
        data.pop(field, None)
    return data
