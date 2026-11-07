from datetime import timedelta
import random
from django.conf import settings
from django.utils import timezone
from .models import LoginAttempt


def check_login_rate_limit(ip_address, email):
    """
    Checks multi-dimensional login rate limits using the database:
    1. By client IP address (e.g. max 5 failed attempts in 5 minutes)
    2. By target account identifier (e.g. max 10 failed attempts across IPs in 15 minutes)

    Returns (is_limited: bool, retry_after_seconds: int)
    """
    now = timezone.now()
    ip_max = getattr(settings, 'LOGIN_RATE_LIMIT_IP_MAX', 5)
    ip_window = getattr(settings, 'LOGIN_RATE_LIMIT_IP_WINDOW', 300)
    account_max = getattr(settings, 'LOGIN_RATE_LIMIT_ACCOUNT_MAX', 10)
    account_window = getattr(settings, 'LOGIN_RATE_LIMIT_ACCOUNT_WINDOW', 900)

    # Opportunistically prune records older than 24 hours
    if random.randint(1, 50) == 1:
        try:
            LoginAttempt.objects.filter(timestamp__lt=now - timedelta(days=1)).delete()
        except Exception:
            pass

    # 1. Check IP limit
    if ip_address:
        ip_cutoff = now - timedelta(seconds=ip_window)
        ip_attempts = LoginAttempt.objects.filter(
            ip_address=ip_address,
            successful=False,
            timestamp__gte=ip_cutoff
        ).order_by('timestamp')

        if ip_attempts.count() >= ip_max:
            oldest_relevant = ip_attempts.first()
            if oldest_relevant:
                elapsed = (now - oldest_relevant.timestamp).total_seconds()
                retry_after = max(1, int(ip_window - elapsed))
                return True, retry_after
            return True, ip_window

    # 2. Check Account limit
    if email:
        email_clean = email.strip().lower()
        account_cutoff = now - timedelta(seconds=account_window)
        account_attempts = LoginAttempt.objects.filter(
            identifier=email_clean,
            successful=False,
            timestamp__gte=account_cutoff
        ).order_by('timestamp')

        if account_attempts.count() >= account_max:
            oldest_relevant = account_attempts.first()
            if oldest_relevant:
                elapsed = (now - oldest_relevant.timestamp).total_seconds()
                retry_after = max(1, int(account_window - elapsed))
                return True, retry_after
            return True, account_window

    return False, 0


def record_login_attempt(ip_address, email, successful=False):
    """
    Records a login attempt in the database.
    If successful, clears recent failed attempts for that IP and email to prevent lockouts.
    """
    ip = ip_address or "0.0.0.0"
    ident = (email or "").strip().lower()

    if successful:
        # Clear failed attempts for this user and IP so legitimate logins reset counters
        LoginAttempt.objects.filter(identifier=ident, successful=False).delete()
        if ip and ip != "0.0.0.0":
            LoginAttempt.objects.filter(ip_address=ip, successful=False).delete()
    else:
        LoginAttempt.objects.create(
            ip_address=ip,
            identifier=ident,
            successful=False
        )

