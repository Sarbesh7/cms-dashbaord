from rest_framework import status
from rest_framework.response import Response

from apps.core.permissions import user_has_permission

PUBLISHED = "published"
TRANSITION_VERBS = {"publish": "Published", "unpublish": "Unpublished", None: "Updated"}


def publish_transition(old_status, new_status):
    """'publish' / 'unpublish' / None for a status change."""
    if new_status == PUBLISHED and old_status != PUBLISHED:
        return "publish"
    if old_status == PUBLISHED and new_status not in (None, PUBLISHED):
        return "unpublish"
    return None


def check_publish_permission(request, module, old_status, new_status):
    """Enforce <module>.publish / <module>.unpublish. Returns (transition, error_response_or_None)."""
    transition = publish_transition(old_status, new_status)
    if transition and not user_has_permission(request.user, f"{module}.{transition}"):
        return transition, Response({"detail": f"You do not have permission to {transition} {module}."},
                                    status=status.HTTP_403_FORBIDDEN)
    return transition, None
