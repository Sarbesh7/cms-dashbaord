"""
Role-aware dashboard overview aggregation.

Each overview module declares the RBAC module it belongs to and a builder that
returns ``{"stats": {...}, "recent": [...]}`` using database aggregation only.
Modules the requesting user cannot view are omitted entirely, and a failure in
one builder never breaks the others (the module is reported as ``{"error": True}``).
"""
import logging
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.core.permissions import effective_role, user_has_permission

logger = logging.getLogger(__name__)

RECENT_LIMIT = 5


def _iso(value):
    return value.isoformat() if value else None


def _status(value):
    return (value or "").lower() or None


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_tenures():
    from apps.tenure.models import Tenure

    today = timezone.localdate()
    qs = Tenure.objects.all()
    active = (
        qs.filter(start_date__lte=today, end_date__gte=today).order_by("-start_date").first()
        or qs.order_by("-start_date").first()
    )
    recent = qs.annotate(member_count=Count("memberships")).order_by("-start_date")[:RECENT_LIMIT]
    return {
        "stats": {
            "total": qs.count(),
            "active_name": active.name if active else None,
        },
        "recent": [
            {
                "id": t.id,
                "slug": t.slug,
                "name": t.name,
                "start_date": _iso(t.start_date),
                "end_date": _iso(t.end_date),
                "member_count": t.member_count,
                "is_active": bool(t.start_date and t.end_date and t.start_date <= today <= t.end_date),
            }
            for t in recent
        ],
    }


def build_members():
    from django.db.models import Prefetch
    from apps.tenure.models import Member, TenureMembership

    qs = Member.objects.all()
    counts = qs.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status__iexact="published")),
    )
    latest_membership = Prefetch(
        "memberships",
        queryset=TenureMembership.objects.select_related("tenure").order_by("-tenure__start_date"),
    )
    recent = qs.order_by("-created_at", "-id").prefetch_related(latest_membership)[:RECENT_LIMIT]
    items = []
    for m in recent:
        memberships = list(m.memberships.all())
        current = memberships[0] if memberships else None
        items.append({
            "id": m.id,
            "slug": m.slug,
            "name": m.name,
            "status": _status(m.status),
            "designation": current.designation if current else None,
            "tenure_name": current.tenure.name if current else None,
            "created_at": _iso(m.created_at),
        })
    return {
        "stats": {
            "total": counts["total"],
            "published": counts["published"],
            "drafts": counts["total"] - counts["published"],
        },
        "recent": items,
    }


def build_alumni():
    from apps.tenure.models import Alumni

    qs = Alumni.objects.select_related("member")
    recent = qs.order_by("-created_at")[:RECENT_LIMIT]
    return {
        "stats": {"total": qs.count()},
        "recent": [
            {
                "id": a.id,
                "name": a.member.name if a.member_id else None,
                "graduation_year": a.graduation_year,
                "created_at": _iso(a.created_at),
            }
            for a in recent
        ],
    }


def build_events():
    from apps.events.models import Event

    today = timezone.localdate()
    qs = Event.objects.all()
    counts = qs.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status__iexact="published")),
        drafts=Count("id", filter=Q(status__iexact="draft")),
        completed=Count("id", filter=Q(status__iexact="completed")),
        upcoming=Count("id", filter=Q(status__iexact="published", date__date__gte=today)),
    )
    recent = (
        qs.annotate(mentor_count=Count("mentors", distinct=True))
        .order_by("-created_at")[:RECENT_LIMIT]
    )
    return {
        "stats": counts,
        "recent": [
            {
                "id": e.id,
                "slug": e.slug,
                "title": e.title,
                "date": _iso(e.date),
                "status": _status(e.status),
                "mentor_count": e.mentor_count,
            }
            for e in recent
        ],
    }


def build_mentors():
    from apps.events.models import Mentor

    qs = Mentor.objects.all()
    counts = qs.aggregate(
        total=Count("id", distinct=True),
        assigned=Count("id", filter=Q(events__isnull=False), distinct=True),
    )
    recent = (
        qs.annotate(event_count=Count("events", distinct=True))
        .order_by("-created_at")[:RECENT_LIMIT]
    )
    return {
        "stats": {
            "total": counts["total"],
            "assigned": counts["assigned"],
        },
        "recent": [
            {
                "id": m.id,
                "name": m.name,
                "expertise": m.expertise or None,
                "event_count": m.event_count,
            }
            for m in recent
        ],
    }


def build_certificates():
    from apps.certificates.models import Certificate

    qs = Certificate.objects.select_related("event")
    counts = qs.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(is_project_completed=True)),
    )
    recent = qs.order_by("-issued_at")[:RECENT_LIMIT]
    return {
        "stats": counts,
        "recent": [
            {
                "id": str(c.certificate_id),
                "full_name": c.full_name,
                "event_title": c.event_title or (c.event.title if c.event_id else None),
                "issued_at": _iso(c.issued_at),
                "is_project_completed": c.is_project_completed,
            }
            for c in recent
        ],
    }


def build_papers():
    from apps.papers.models import PastPaper

    qs = PastPaper.objects.all()
    counts = qs.aggregate(
        total=Count("id"),
        old_course=Count("id", filter=Q(is_old_course=True)),
    )
    recent = qs.order_by("-created_at")[:RECENT_LIMIT]
    items = []
    for p in recent:
        get_display = getattr(p, "get_subject_name_display", None)
        items.append({
            "id": p.id,
            "slug": p.slug,
            "subject": get_display() if callable(get_display) else p.subject_name,
            "subject_code": p.subject_name,
            "semester": p.semester,
            "exam_year": p.exam_year,
            "is_old_course": p.is_old_course,
        })
    return {
        "stats": {
            "total": counts["total"],
            "old_course": counts["old_course"],
            "current_course": counts["total"] - counts["old_course"],
        },
        "recent": items,
    }


def build_blogs():
    from apps.blogs.models import Blog

    qs = Blog.objects.all()
    counts = qs.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status__iexact="published")),
        drafts=Count("id", filter=Q(status__iexact="draft")),
    )
    recent = qs.select_related("author").order_by("-created_at")[:RECENT_LIMIT]
    return {
        "stats": counts,
        "recent": [
            {
                "id": b.id,
                "slug": b.slug,
                "title": b.title,
                "status": _status(b.status),
                "featured_image_url": b.featured_image_url or None,
                "author_name": b.author.name if b.author_id else None,
                "published_at": _iso(b.published_at),
                "created_at": _iso(b.created_at),
            }
            for b in recent
        ],
    }


def build_notices():
    from apps.notices.models import Notice

    qs = Notice.objects.all()
    counts = qs.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status__iexact="published")),
    )
    recent = qs.order_by("-created_at")[:RECENT_LIMIT]
    return {
        "stats": {
            "total": counts["total"],
            "published": counts["published"],
            "drafts": counts["total"] - counts["published"],
        },
        "recent": [
            {
                "id": n.id,
                "slug": n.slug,
                "title": n.title,
                "status": _status(n.status) or "draft",
                "category": n.category or None,
                "created_at": _iso(n.created_at),
            }
            for n in recent
        ],
    }


def activity_log_summary():
    """Shared by the overview and the activity-log summary endpoint."""
    from apps.core.models import ActivityLog

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_ago = now - timedelta(days=30)

    most_active = (
        ActivityLog.objects.filter(timestamp__gte=month_ago)
        .values("module")
        .annotate(count=Count("id"))
        .order_by("-count")
        .first()
    )
    aggregated_counts = ActivityLog.objects.aggregate(
        total_activities=Count("id"),
        logins_this_week=Count("id", filter=Q(action="login", timestamp__gte=week_ago)),
        mutations_today=Count(
            "id",
            filter=Q(
                action__in=[
                    "create", "update", "delete", "publish", "unpublish",
                    "status_change", "role_change", "media_upload", "media_delete"
                ],
                timestamp__gte=today_start,
            ),
        ),
    )
    return {
        "total_activities": aggregated_counts.get("total_activities") or 0,
        "logins_this_week": aggregated_counts.get("logins_this_week") or 0,
        "mutations_today": aggregated_counts.get("mutations_today") or 0,
        "most_active_module": most_active["module"] if most_active else "None",
    }


def build_activity_logs():
    from apps.core.models import ActivityLog

    recent = ActivityLog.objects.order_by("-timestamp")[:RECENT_LIMIT]
    return {
        "stats": activity_log_summary(),
        "recent": [
            {
                "id": log.id,
                "user_email": log.user_email_snapshot,
                "user_name": log.actor_name_snapshot or log.user_email_snapshot,
                "action": log.action,
                "module": log.module,
                "target_repr": log.target_repr,
                "timestamp": _iso(log.timestamp),
            }
            for log in recent
        ],
    }


# Overview key -> (exact permission required, builder). Order is the display order.
OVERVIEW_MODULES = {
    "tenures": ("tenures.view", build_tenures),
    "members": ("members.view", build_members),
    "alumni": ("alumni.view", build_alumni),
    "events": ("events.view", build_events),
    "mentors": ("mentors.view", build_mentors),
    "certificates": ("certificates.view", build_certificates),
    "papers": ("papers.view", build_papers),
    "blogs": ("blogs.view", build_blogs),
    "notices": ("notices.view", build_notices),
    "activity_logs": ("activity_logs.view", build_activity_logs),
}


def build_overview(user):
    role = effective_role(user) or ""
    modules = {}
    if not user_has_permission(user, "dashboard.stats.view"):
        return {"role": role, "modules": modules}
    for key, (permission, builder) in OVERVIEW_MODULES.items():
        if not user_has_permission(user, permission):
            continue
        try:
            modules[key] = builder()
        except Exception:  # isolate failures so partial data still renders
            logger.exception("Dashboard overview module %s failed", key)
            modules[key] = {"error": True}
    return {"role": role, "modules": modules}


DASHBOARD_OVERVIEW_CACHE_TIMEOUT = 60  # seconds


def get_cached_dashboard_overview(user):
    from django.core.cache import cache
    from apps.core.cache import get_dashboard_overview_cache_version

    if not user or not user.is_authenticated:
        return build_overview(user)

    role = effective_role(user) or ""
    version = get_dashboard_overview_cache_version()
    cache_key = f"dashboard_overview_{user.id}_{role}_v{version}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = build_overview(user)
    cache.set(cache_key, data, DASHBOARD_OVERVIEW_CACHE_TIMEOUT)
    return data

