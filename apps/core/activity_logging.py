"""
Append-only activity logging.

* ``log_activity`` records one successful logical action. It never raises, so a
  logging failure cannot break the operation being logged.
* ``model_snapshot`` / ``diff_snapshots`` build before/after values for updates.
  Sensitive fields (passwords, tokens, secrets) are never recorded.
* ``get_client_ip`` trusts forwarded-IP headers only when the direct peer
  (REMOTE_ADDR) is an explicitly configured trusted proxy (settings.TRUSTED_PROXIES).
"""
import ipaddress
import logging
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.db.models.fields.files import FieldFile

logger = logging.getLogger('activity_logs')

SENSITIVE_KEYS = ("password", "token", "secret", "api_key", "apikey", "authorization", "cookie", "otp")
MAX_VALUE_LENGTH = 500


def _trusted_networks():
    networks = []
    for entry in getattr(settings, "TRUSTED_PROXIES", []) or []:
        try:
            networks.append(ipaddress.ip_network(entry.strip(), strict=False))
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXIES entry")
    return networks


def _parse_ip(value):
    try:
        return str(ipaddress.ip_address((value or "").strip()))
    except ValueError:
        return None


def _is_trusted(ip, networks):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def get_client_ip(request):
    """
    Resolve the client IP without trusting client-controlled headers.

    REMOTE_ADDR is the direct TCP peer. Forwarded headers are consulted only when
    that peer is a configured trusted proxy:
      * CLIENT_IP_HEADER (e.g. "CF-Connecting-IP") is used when configured, or
      * X-Forwarded-For is walked from the right, skipping trusted proxies; the
        first untrusted hop is the client (left-most values are client-supplied).
    """
    if not request:
        return None
    meta = request.META
    remote = _parse_ip(meta.get("REMOTE_ADDR"))
    networks = _trusted_networks()
    if not remote or not networks or not _is_trusted(remote, networks):
        return remote

    header = getattr(settings, "CLIENT_IP_HEADER", "") or ""
    if header:
        value = _parse_ip(meta.get("HTTP_" + header.upper().replace("-", "_")))
        if value:
            return value

    forwarded = [h.strip() for h in meta.get("HTTP_X_FORWARDED_FOR", "").split(",") if h.strip()]
    for hop in reversed(forwarded):
        ip = _parse_ip(hop)
        if ip is None:
            break  # malformed chain: stop rather than guess
        if not _is_trusted(ip, networks):
            return ip
    return remote


def _is_sensitive(key):
    key = str(key).lower()
    return any(s in key for s in SENSITIVE_KEYS)


def _clean(value):
    if isinstance(value, FieldFile):
        return value.name or None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: ("[redacted]" if _is_sensitive(k) else _clean(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value][:50]
    if isinstance(value, str) and len(value) > MAX_VALUE_LENGTH:
        return value[:MAX_VALUE_LENGTH] + "…"
    if value is None or isinstance(value, (int, float, bool, str)):
        return value
    return str(value)


def model_snapshot(instance, fields=None, exclude=()):
    """Plain-value snapshot of concrete model fields (sensitive fields skipped)."""
    if instance is None:
        return {}
    data = {}
    for field in instance._meta.concrete_fields:
        name = field.name
        if (fields and name not in fields) or name in exclude or _is_sensitive(name):
            continue
        if name in ("created_at", "updated_at", "last_login"):
            continue
        value = getattr(instance, field.attname)
        data[name] = _clean(value)
    return data


def diff_snapshots(before, after):
    """{field: {"before": old, "after": new}} for fields whose value changed."""
    changes = {}
    for key in set(before) | set(after):
        old, new = before.get(key), after.get(key)
        if old != new:
            changes[key] = {"before": old, "after": new}
    return changes


def log_activity(request=None, user=None, action="", module="", target_id="", target_repr="",
                 details=None, description="", changes=None):
    """Record one successful action. Never raises."""
    from apps.core.models import ActivityLog
    from apps.core.permissions import effective_role

    try:
        acting_user = user
        if not acting_user and request is not None:
            req_user = getattr(request, "user", None)
            if req_user is not None and req_user.is_authenticated:
                acting_user = req_user

        actor_name = ""
        user_email = ""
        user_role = ""
        actor_id = None
        if acting_user:
            actor_id = acting_user.pk
            actor_name = (acting_user.get_full_name() or acting_user.username or "").strip()
            user_email = getattr(acting_user, 'email', '') or ''
            user_role = effective_role(acting_user) or getattr(acting_user, 'role', '') or ''

        ip = get_client_ip(request) if request is not None else None
        user_agent = (request.META.get('HTTP_USER_AGENT', '') if request is not None else '')[:500]

        return ActivityLog.objects.create(
            user=acting_user if acting_user and acting_user.pk else None,
            actor_id_snapshot=actor_id,
            actor_name_snapshot=actor_name[:255],
            user_email_snapshot=user_email[:255],
            user_role_snapshot=user_role[:50],
            action=action,
            module=module,
            target_id=str(target_id) if target_id not in (None, "") else "",
            target_repr=str(target_repr)[:255] if target_repr else "",
            description=description or "",
            changes=_clean(changes or {}),
            details=_clean(details or {}),
            ip_address=ip,
            user_agent=user_agent,
        )
    except Exception as e:  # logging must never break the action being logged
        logger.warning(f"Failed to record activity log for module '{module}', action '{action}': {e}")
        return None
