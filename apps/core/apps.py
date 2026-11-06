from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        from django.db.models.signals import m2m_changed, post_delete, post_save
        from apps.core.cache import bump_content_cache_version
        from apps.events.models import Event, EventMentorAssignment, Mentor
        from apps.notices.models import Notice
        from apps.tenure.models import Alumni, Member, Tenure, TenureMembership

        # Any write to cached public content invalidates the cached GET responses.
        for model in (Event, Mentor, EventMentorAssignment, Notice, Tenure, Member, TenureMembership, Alumni):
            post_save.connect(bump_content_cache_version, sender=model, dispatch_uid=f"cache-save-{model.__name__}")
            post_delete.connect(bump_content_cache_version, sender=model, dispatch_uid=f"cache-delete-{model.__name__}")
        m2m_changed.connect(
            bump_content_cache_version, sender=Alumni.tenures.through, dispatch_uid="cache-m2m-alumni-tenures"
        )
