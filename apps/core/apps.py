from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        from django.db.models.signals import m2m_changed, post_delete, post_save
        from apps.core.cache import bump_content_cache_version, bump_dashboard_overview_cache_version
        from apps.events.models import Event, EventMentorAssignment, Mentor
        from apps.notices.models import Notice
        from apps.tenure.models import Alumni, Member, Tenure, TenureMembership
        from apps.certificates.models import Certificate
        from apps.papers.models import PastPaper
        from apps.blogs.models import Blog

        # Any write to cached public content invalidates the cached GET responses.
        content_models = (Event, Mentor, EventMentorAssignment, Notice, Tenure, Member, TenureMembership, Alumni)
        for model in content_models:
            post_save.connect(bump_content_cache_version, sender=model, dispatch_uid=f"cache-save-{model.__name__}")
            post_delete.connect(bump_content_cache_version, sender=model, dispatch_uid=f"cache-delete-{model.__name__}")
        m2m_changed.connect(
            bump_content_cache_version, sender=Alumni.tenures.through, dispatch_uid="cache-m2m-alumni-tenures"
        )

        # Invalidate dashboard overview cache on any write to dashboard entities.
        dashboard_models = (
            Event, Mentor, EventMentorAssignment, Notice, Tenure, Member,
            TenureMembership, Alumni, Certificate, PastPaper, Blog
        )
        for model in dashboard_models:
            post_save.connect(bump_dashboard_overview_cache_version, sender=model, dispatch_uid=f"dash-save-{model.__name__}")
            post_delete.connect(bump_dashboard_overview_cache_version, sender=model, dispatch_uid=f"dash-delete-{model.__name__}")
        m2m_changed.connect(
            bump_dashboard_overview_cache_version, sender=Alumni.tenures.through, dispatch_uid="dash-m2m-alumni-tenures"
        )
