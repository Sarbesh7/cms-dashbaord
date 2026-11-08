"""
Regression tests for the security remediation (findings S1-S12) and the RBAC model.
"""
import shutil
import tempfile
import uuid
from io import BytesIO

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from apps.blogs.models import Blog
from apps.blogs.validators import validate_markdown_content
from apps.certificates.models import Certificate, CertificateTemplate
from apps.core.activity_logging import get_client_ip
from apps.core.models import ActivityLog, ImmutableLogError
from apps.core.permissions import (
    ALL_PERMISSIONS, PROTECTED_PERMISSIONS, ROLE_DEFINITIONS, ROLE_PERMISSIONS, has_permission,
)
from apps.events.models import Event, Mentor
from apps.notices.models import Notice
from apps.tenure.models import Alumni, Member, Tenure, TenureMembership
from apps.users.models import User

TRUSTED = "http://localhost:3000"
PASSWORD = "Str0ng-Passphrase-91!"


def make_user(role, email=None, **extra):
    email = email or f"{role}-{uuid.uuid4().hex[:6]}@example.org"
    return User.objects.create_user(username=email.split("@")[0], email=email, password=PASSWORD, role=role, **extra)


def png_bytes():
    buf = BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    return buf.getvalue()


def login(client, user, origin=TRUSTED):
    res = client.post("/api/v1/login/", {"email": user.email, "password": PASSWORD}, HTTP_ORIGIN=origin)
    assert res.status_code == 200, res.data
    return res


# ----------------------------------------------------------------------------- RBAC
class RBACCatalogTests(TestCase):
    MODULE_ACCESS = {
        "superadmin": {"tenures", "members", "alumni", "events", "mentors", "notices", "blogs", "certificates",
                       "papers", "accounts", "activity_logs", "admin_access"},
        "admin": {"tenures", "members", "alumni", "events", "mentors", "notices", "blogs", "certificates",
                  "papers", "activity_logs", "admin_access"},
        "cms_user": {"tenures", "members", "alumni", "events", "mentors", "notices", "blogs", "certificates", "papers"},
        "operations": {"events", "notices", "certificates", "papers", "mentors"},
        "papers": {"papers"},
        "notice": {"notices"},
        "blog": {"blogs"},
    }

    def test_exactly_seven_predefined_roles(self):
        self.assertEqual(list(ROLE_DEFINITIONS), ["superadmin", "admin", "cms_user", "operations", "papers", "notice", "blog"])

    def test_view_access_matrix_for_every_role(self):
        modules = {"tenures", "members", "alumni", "events", "mentors", "notices", "blogs", "certificates",
                   "papers", "accounts", "activity_logs", "admin_access"}
        for role, allowed in self.MODULE_ACCESS.items():
            for module in modules:
                self.assertEqual(has_permission(role, f"{module}.view"), module in allowed, (role, module))
            self.assertTrue(has_permission(role, "dashboard.view"), role)

    def test_protected_permissions_never_leak_through_wildcards(self):
        for role, perms in ROLE_PERMISSIONS.items():
            for perm, roles in PROTECTED_PERMISSIONS.items():
                if role not in roles:
                    self.assertNotIn(perm, perms, (role, perm))
        self.assertFalse(has_permission("admin", "members.delete"))
        self.assertFalse(has_permission("cms_user", "members.delete"))
        self.assertTrue(has_permission("superadmin", "members.delete"))
        self.assertFalse(has_permission("admin", "accounts.manage"))
        self.assertTrue(has_permission("admin", "activity_logs.view"))

    def test_exact_matching_only(self):
        self.assertFalse(has_permission("superadmin", "events.creat"))
        self.assertFalse(has_permission("superadmin", "events"))
        self.assertFalse(has_permission("superadmin", "events.*"))
        self.assertFalse(has_permission("unknown", "events.view"))
        self.assertTrue(all(p in ALL_PERMISSIONS for perms in ROLE_PERMISSIONS.values() for p in perms))

    def test_publish_permissions_for_blog_and_notice_roles(self):
        self.assertTrue(has_permission("blog", "blogs.publish") and has_permission("blog", "blogs.unpublish"))
        self.assertTrue(has_permission("notice", "notices.publish") and has_permission("notice", "notices.unpublish"))
        self.assertFalse(has_permission("blog", "notices.publish"))

    def test_api_matrix_for_all_roles(self):
        client = APIClient()
        expectations = {
            "/api/v1/certificates/": {"superadmin", "admin", "cms_user", "operations"},
            "/api/v1/activity-logs/": {"superadmin", "admin"},
            "/api/v1/users/accounts/": {"superadmin", "admin"},
            "/api/v1/blogs/": {"superadmin", "admin", "cms_user", "blog"},
            "/api/v1/certificates/templates/": {"superadmin", "admin", "cms_user", "operations"},
        }
        for role in ROLE_DEFINITIONS:
            client.force_authenticate(make_user(role))
            for url, allowed in expectations.items():
                code = client.get(url).status_code
                self.assertEqual(code == 200, role in allowed, (role, url, code))

    def test_role_escalation_via_payload_blocked(self):
        client = APIClient()
        admin = make_user("admin")
        client.force_authenticate(admin)
        self.assertEqual(client.patch(f"/api/v1/users/accounts/{admin.id}/", {"role": "superadmin"}).status_code, 403)
        cms = make_user("cms_user")
        client.force_authenticate(cms)
        res = client.post("/api/v1/members/", {"name": "X", "email": "x@example.org", "is_superuser": True})
        self.assertIn(res.status_code, (201, 400))
        cms.refresh_from_db()
        self.assertFalse(cms.is_superuser)

    def test_me_and_roles_endpoints(self):
        client = APIClient()
        user = make_user("notice")
        client.force_authenticate(user)
        me = client.get("/api/v1/users/me/").data
        self.assertEqual(me["role"], "notice")
        self.assertEqual(me["role_label"], ROLE_DEFINITIONS["notice"]["label"])
        self.assertIn("notices.publish", me["permissions"])
        self.assertNotIn("blogs.view", me["permissions"])
        self.assertEqual(len(client.get("/api/v1/users/roles/").data), 7)


# ----------------------------------------------------------------------------- S1
class BlogContentSanitizationTests(TestCase):
    MALICIOUS = [
        "<iframe srcdoc='<script>alert(1)</script>'></iframe>",
        "Intro `\n\n<iframe srcdoc=\"&lt;script&gt;x&lt;/script&gt;\"></iframe>\n\nend ` text",
        "Intro `\n<iframe srcdoc=\"x\"></iframe>\nend `",
        "```\ncode\n````\n<iframe srcdoc=\"x\"></iframe>",
        "```\ncode\n   ```\n<iframe srcdoc=\"x\"></iframe>",
        "`<iframe srcdoc=\"x\">``",
        "\\`<iframe srcdoc=\"x\">`",
        "<!-- --!><iframe srcdoc=\"x\"></iframe> -->",
        "<img src=x onerror=alert(1)>",
        "<a href=\"javascript:alert(1)\">x</a>",
        "[x](javascript:alert(1))",
        "<u onclick=\"alert(1)\">x</u>",
        "<svg onload=alert(1)>",
    ]
    LEGITIMATE = (
        "# Heading\n\nParagraph with **bold**, _italic_, <u>underline</u> and a line<br>break.\n\n"
        "- item one\n- item two\n\n1. first\n\n"
        "[A link](https://example.org) and [relative](/blogs/x) and [mail](mailto:a@b.org)\n\n"
        "![Alt](https://res.cloudinary.com/demo/image/upload/sample.jpg)\n\n"
        "Inline `<div>` is code.\n\n```html\n<script>shown as code</script>\n```\n"
    )

    def test_malicious_payloads_rejected(self):
        for payload in self.MALICIOUS:
            with self.assertRaises(ValidationError, msg=payload):
                validate_markdown_content(payload)

    def test_legitimate_rich_content_accepted(self):
        self.assertEqual(validate_markdown_content(self.LEGITIMATE), self.LEGITIMATE)

    def test_api_rejects_bypass_payload_from_blog_role(self):
        client = APIClient()
        client.force_authenticate(make_user("blog"))
        res = client.post("/api/v1/blogs/", {"title": "x", "content": self.MALICIOUS[1]}, format="json")
        self.assertEqual(res.status_code, 400)


# ----------------------------------------------------------------------------- S2
@override_settings(CORS_ALLOWED_ORIGINS=[TRUSTED], CSRF_TRUSTED_ORIGINS=[TRUSTED])
class CookieCsrfTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superadmin = make_user("superadmin")
        login(self.client, self.superadmin)
        self.payload = {"username": "evil", "email": "evil@example.org", "password": PASSWORD, "role": "admin"}

    def test_cross_site_form_post_rejected(self):
        res = self.client.post("/api/v1/users/accounts/", self.payload, HTTP_ORIGIN="https://attacker.example")
        self.assertEqual(res.status_code, 403)
        self.assertFalse(User.objects.filter(email="evil@example.org").exists())

    def test_missing_origin_rejected_for_cookie_auth(self):
        res = self.client.post("/api/v1/users/accounts/", self.payload)
        self.assertEqual(res.status_code, 403)

    def test_referer_from_untrusted_site_rejected(self):
        res = self.client.post("/api/v1/users/accounts/", self.payload, HTTP_REFERER="https://attacker.example/p")
        self.assertEqual(res.status_code, 403)

    def test_trusted_dashboard_origin_allowed(self):
        res = self.client.post("/api/v1/users/accounts/", self.payload, HTTP_ORIGIN=TRUSTED)
        self.assertEqual(res.status_code, 201, res.data)

    def test_safe_methods_and_bearer_header_not_blocked(self):
        self.assertEqual(self.client.get("/api/v1/users/me/").status_code, 200)
        access = self.client.cookies["access_token"].value
        bearer = APIClient()
        res = bearer.post("/api/v1/users/accounts/", self.payload, HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(res.status_code, 201)

    def test_login_from_untrusted_origin_rejected(self):
        res = APIClient().post("/api/v1/login/", {"email": self.superadmin.email, "password": PASSWORD},
                               HTTP_ORIGIN="https://attacker.example")
        self.assertEqual(res.status_code, 403)

    def test_cookie_attributes(self):
        cookie = self.client.cookies["access_token"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")


# ----------------------------------------------------------------------------- S3 / S10 / S11
@override_settings(CORS_ALLOWED_ORIGINS=[TRUSTED], CSRF_TRUSTED_ORIGINS=[TRUSTED])
class CredentialInvalidationTests(TestCase):
    def setUp(self):
        self.user = make_user("cms_user")
        self.device_a = APIClient()
        self.device_b = APIClient()
        login(self.device_a, self.user)
        login(self.device_b, self.user)
        self.old_access = self.device_b.cookies["access_token"].value
        self.other = make_user("cms_user")
        self.other_client = APIClient()
        login(self.other_client, self.other)

    def _assert_device_b_locked_out(self):
        self.assertEqual(self.device_b.get("/api/v1/users/me/").status_code, 401)
        bearer = APIClient()
        self.assertEqual(bearer.get("/api/v1/users/me/", HTTP_AUTHORIZATION=f"Bearer {self.old_access}").status_code, 401)
        self.assertEqual(self.device_b.post("/api/v1/users/refresh-token/", HTTP_ORIGIN=TRUSTED).status_code, 401)
        # Unrelated users keep their sessions.
        self.assertEqual(self.other_client.get("/api/v1/users/me/").status_code, 200)

    def test_self_password_change_signs_out_other_devices(self):
        res = self.device_a.post("/api/v1/users/change-password/",
                                 {"old_password": PASSWORD, "new_password": "An0ther-Strong-Pass!"}, HTTP_ORIGIN=TRUSTED)
        self.assertEqual(res.status_code, 200)
        self._assert_device_b_locked_out()
        self.assertEqual(self.device_a.get("/api/v1/users/me/").status_code, 200)  # fresh cookies issued

    def test_superadmin_password_change_signs_out_target(self):
        admin_client = APIClient()
        login(admin_client, make_user("superadmin"))
        res = admin_client.patch(f"/api/v1/users/accounts/{self.user.id}/", {"password": "Admin-Set-Pass-77!"},
                                 HTTP_ORIGIN=TRUSTED)
        self.assertEqual(res.status_code, 200, res.data)
        self._assert_device_b_locked_out()
        self.assertTrue(ActivityLog.objects.filter(action="password_change", module="accounts").exists())

    def test_inactive_user_gets_generic_login_failure(self):
        self.user.is_active = False
        self.user.save()
        res = APIClient().post("/api/v1/login/", {"email": self.user.email, "password": PASSWORD})
        self.assertEqual(res.status_code, 401)
        self.assertNotIn("access_token", res.cookies)

    def test_weak_and_common_passwords_rejected(self):
        res = self.device_a.post("/api/v1/users/change-password/",
                                 {"old_password": PASSWORD, "new_password": "password123"}, HTTP_ORIGIN=TRUSTED)
        self.assertEqual(res.status_code, 400)
        client = APIClient()
        client.force_authenticate(make_user("superadmin"))
        res = client.post("/api/v1/users/accounts/",
                          {"username": "u1", "email": "u1@example.org", "password": "12345678", "role": "blog"})
        self.assertEqual(res.status_code, 400)


# ----------------------------------------------------------------------------- S4
class MediaDeletionTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)
        self.client = APIClient()
        self.blogger = make_user("blog")
        self.client.force_authenticate(self.blogger)

    def test_blog_role_cannot_delete_other_module_media(self):
        template = CertificateTemplate.objects.create(template_name="T", template_file=ContentFile(b"x", name="t.png"))
        name = template.template_file.name
        orphan = default_storage.save("certificate_templates/orphan.png", ContentFile(b"x"))
        for public_id in (name, orphan):
            res = self.client.post("/api/v1/blogs/delete-image/", {"public_id": public_id}, format="json")
            self.assertEqual(res.status_code, 403, public_id)
            res = self.client.post("/api/v1/media/delete/", {"public_id": public_id}, format="json")
            self.assertEqual(res.status_code, 403, public_id)
            self.assertTrue(default_storage.exists(public_id))

    def test_unreferenced_blog_image_deleted_and_referenced_kept(self):
        up = self.client.post("/api/v1/blogs/upload-image/", {"image": ContentFile(png_bytes(), name="a.png")},
                              format="multipart")
        self.assertEqual(up.status_code, 201)
        pid = up.data["public_id"]
        member = Member.objects.create(name="Author", email="author@example.org")
        Blog.objects.create(title="Uses it", author=member, content="x", featured_image_public_id=pid)
        res = self.client.post("/api/v1/blogs/delete-image/", {"public_id": pid}, format="json")
        self.assertEqual(res.status_code, 409)
        self.assertTrue(default_storage.exists(pid))
        Blog.objects.all().delete()
        res = self.client.post("/api/v1/blogs/delete-image/", {"public_id": pid}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(default_storage.exists(pid))
        self.assertTrue(ActivityLog.objects.filter(action="media_delete").exists())

    def test_invalid_and_external_ids_never_reach_storage(self):
        for bad in ("https://cdn.example.org/a.png", "../settings.py", "blogs/../../x", "/etc/passwd"):
            res = self.client.post("/api/v1/media/delete/", {"public_id": bad}, format="json")
            self.assertEqual(res.status_code, 400, bad)
        res = self.client.post("/api/v1/blogs/delete-image/", {"url": "https://cdn.example.org/a.png"}, format="json")
        self.assertEqual(res.status_code, 200)

    def test_usage_endpoint_reports_references(self):
        Event.objects.create(title="E", description="d", date=timezone.now(), image="events_templates/e.png")
        client = APIClient()
        client.force_authenticate(make_user("operations"))
        res = client.get("/api/v1/media/usage/", {"public_id": "events_templates/e.png"})
        self.assertTrue(res.data["in_use"])
        self.assertEqual(res.data["references"][0]["label"], "E")


# ----------------------------------------------------------------------------- S5 / S6
class PublicVisibilityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.anon = APIClient()
        now = timezone.now()
        self.pub_event = Event.objects.create(title="Pub", description="d", date=now, status="published")
        self.draft_event = Event.objects.create(title="Secret Draft", description="d", date=now, status="draft")
        mentor = Mentor.objects.create(name="M", email="mentor@private.org", expertise="x")
        self.pub_event.mentor_assignments.create(mentor=mentor)
        self.draft_event.mentor_assignments.create(mentor=mentor)
        Notice.objects.create(title="Public notice", description="d", status="published")
        self.draft_notice = Notice.objects.create(title="Draft notice", description="d", status="draft")
        self.pub_member = Member.objects.create(name="Pub M", email="pub@private.org", status="published")
        self.draft_member = Member.objects.create(name="Draft M", email="draft@private.org", status="draft")
        self.tenure = Tenure.objects.create(name="T", slug="t", start_date=now.date(), end_date=now.date(),
                                            signature="president_signatures/s.png")
        TenureMembership.objects.create(member=self.pub_member, tenure=self.tenure, designation="P")
        TenureMembership.objects.create(member=self.draft_member, tenure=self.tenure, designation="Q")

    def test_anonymous_sees_only_published_and_no_private_fields(self):
        events = self.anon.get("/api/v1/events/").data["results"]
        self.assertEqual([e["title"] for e in events], ["Pub"])
        self.assertNotIn("mentor_email", str(events))
        self.assertEqual(self.anon.get(f"/api/v1/events/{self.draft_event.slug}/").status_code, 404)
        mentors = self.anon.get("/api/v1/mentors/").data["results"]
        self.assertNotIn("mentor@private.org", str(mentors))
        self.assertNotIn("Secret Draft", str(mentors))
        self.assertEqual([n["title"] for n in self.anon.get("/api/v1/notices/").data["results"]], ["Public notice"])
        self.assertEqual(self.anon.get(f"/api/v1/notices/{self.draft_notice.id}/").status_code, 404)
        members = self.anon.get("/api/v1/members/").data["results"]
        self.assertEqual([m["name"] for m in members], ["Pub M"])
        self.assertNotIn("@private.org", str(members))
        self.assertEqual(self.anon.get(f"/api/v1/members/{self.draft_member.slug}/").status_code, 404)
        tenure = self.anon.get("/api/v1/tenures/t/").data
        self.assertNotIn("signature", tenure)
        self.assertEqual([m["member_name"] for m in tenure["memberships"]], ["Pub M"])

    def test_authentication_without_module_permission_gets_public_view(self):
        client = APIClient()
        client.force_authenticate(make_user("blog"))
        self.assertEqual(len(client.get("/api/v1/events/").data["results"]), 1)

    def test_privileged_role_sees_drafts_and_cache_does_not_leak(self):
        self.anon.get("/api/v1/events/")  # warm the public cache
        staff = APIClient()
        staff.force_authenticate(make_user("operations"))
        self.assertEqual(len(staff.get("/api/v1/events/").data["results"]), 2)
        self.assertEqual(len(self.anon.get("/api/v1/events/").data["results"]), 1)

    def test_certificate_listing_protected_and_verification_single_record(self):
        cert = Certificate.objects.create(full_name="Holder", event=self.pub_event)
        Certificate.objects.create(full_name="Someone Else", event=self.pub_event)
        self.assertEqual(self.anon.get("/api/v1/certificates/").status_code, 401)
        self.assertEqual(self.anon.get(f"/api/v1/certificates/{cert.certificate_id}/").status_code, 401)
        res = self.anon.get(f"/api/v1/certificates/verify/{cert.certificate_id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["certificate"]["full_name"], "Holder")
        self.assertEqual(set(res.data["certificate"]), {"certificate_id", "full_name", "event_title",
                                                       "is_project_completed", "issued_at"})
        self.assertNotIn("Someone Else", str(res.data))
        self.assertEqual(self.anon.get(f"/api/v1/certificates/verify/{uuid.uuid4()}/").status_code, 404)
        self.assertEqual(self.anon.get("/api/v1/certificates/verify/not-a-uuid/").status_code, 400)


# ----------------------------------------------------------------------------- S8 / S9
class LandingPageAndIpTests(TestCase):
    def test_landing_page_has_no_default_credentials(self):
        body = self.client.get("/").content.decode()
        self.assertNotIn("<code>admin</code>", body)

    def _request(self, remote, xff=None, cf=None):
        meta = {"REMOTE_ADDR": remote}
        if xff:
            meta["HTTP_X_FORWARDED_FOR"] = xff
        if cf:
            meta["HTTP_CF_CONNECTING_IP"] = cf
        return RequestFactory().get("/", **meta)

    def test_untrusted_peer_cannot_spoof_ip(self):
        with override_settings(TRUSTED_PROXIES=[]):
            self.assertEqual(get_client_ip(self._request("203.0.113.9", xff="1.2.3.4")), "203.0.113.9")

    def test_trusted_proxy_chain_walked_from_the_right(self):
        with override_settings(TRUSTED_PROXIES=["10.0.0.0/8"], CLIENT_IP_HEADER=""):
            req = self._request("10.0.0.5", xff="6.6.6.6, 198.51.100.7, 10.0.0.9")
            self.assertEqual(get_client_ip(req), "198.51.100.7")

    def test_configured_client_ip_header_used_only_from_trusted_proxy(self):
        with override_settings(TRUSTED_PROXIES=["10.0.0.0/8"], CLIENT_IP_HEADER="CF-Connecting-IP"):
            self.assertEqual(get_client_ip(self._request("10.0.0.5", cf="198.51.100.8")), "198.51.100.8")
            self.assertEqual(get_client_ip(self._request("203.0.113.9", cf="1.1.1.1")), "203.0.113.9")


# ----------------------------------------------------------------------------- activity logs / member deletion
class ActivityLogIntegrityTests(TestCase):
    def test_logs_are_immutable_at_the_model_layer(self):
        user = make_user("admin")
        client = APIClient()
        login(client, user)
        log = ActivityLog.objects.get(action="login")
        log.action = "tampered"
        with self.assertRaises(ImmutableLogError):
            log.save()
        with self.assertRaises(ImmutableLogError):
            log.delete()
        with self.assertRaises(ImmutableLogError):
            ActivityLog.objects.all().update(action="x")
        with self.assertRaises(ImmutableLogError):
            ActivityLog.objects.all().delete()
        user.delete()  # SET_NULL is still allowed
        self.assertEqual(ActivityLog.objects.get(pk=log.pk).user_email_snapshot, user.email)

    def test_login_logged_once_without_secrets_and_updates_capture_changes(self):
        user = make_user("cms_user")
        login(APIClient(), user)
        self.assertEqual(ActivityLog.objects.filter(action="login").count(), 1)
        self.assertNotIn(PASSWORD, str(list(ActivityLog.objects.values())))
        client = APIClient()
        client.force_authenticate(user)
        event = Event.objects.create(title="Old", description="d", date=timezone.now())
        client.patch(f"/api/v1/events/{event.id}/", {"title": "New"}, format="json")
        log = ActivityLog.objects.get(action="update", module="events")
        self.assertEqual(log.changes["title"], {"before": "Old", "after": "New"})
        self.assertEqual(log.actor_name_snapshot, "Name unavailable")
        self.assertEqual(log.actor_username_snapshot, user.username)

    def test_activity_log_ordering_and_filters(self):
        client = APIClient()
        client.force_authenticate(make_user("admin"))
        self.assertEqual(client.get("/api/v1/activity-logs/", {"ordering": "module"}).status_code, 200)
        self.assertEqual(client.get("/api/v1/activity-logs/", {"start_date": "nope"}).status_code, 400)


class MemberDeletionPreservationTests(TestCase):
    def test_superadmin_only_and_history_preserved(self):
        member = Member.objects.create(name="Former Head", email="head@example.org")
        tenure = Tenure.objects.create(name="2024", slug="tenure-2024", start_date=timezone.now().date(),
                                       end_date=timezone.now().date())
        membership = TenureMembership.objects.create(member=member, tenure=tenure, designation="President")
        alumni = Alumni.objects.create(member=member, graduation_year=2024)
        blog = Blog.objects.create(title="Old article", author=member, content="x", status="published")

        client = APIClient()
        for role in ("admin", "cms_user"):
            client.force_authenticate(make_user(role))
            self.assertEqual(client.delete(f"/api/v1/members/{member.slug}/").status_code, 403)
        client.force_authenticate(make_user("superadmin"))
        self.assertEqual(client.delete(f"/api/v1/members/{member.slug}/").status_code, 204)

        membership.refresh_from_db()
        alumni.refresh_from_db()
        blog.refresh_from_db()
        self.assertIsNone(membership.member)
        self.assertEqual(membership.member_name, "Former Head")
        self.assertEqual(alumni.member_name, "Former Head")
        self.assertEqual(blog.author_name_snapshot, "Former Head")
        tenure_data = client.get("/api/v1/tenures/tenure-2024/").data
        self.assertEqual(tenure_data["memberships"][0]["member_name"], "Former Head")
        self.assertEqual(client.get(f"/api/v1/alumni/{alumni.id}/").status_code, 200)


# ----------------------------------------------------------------------------- dashboard / duplicates
class DashboardOverviewAndDuplicateTests(TestCase):
    EXPECTED = {
        "superadmin": {"tenures", "members", "alumni", "events", "mentors", "certificates", "papers", "blogs",
                       "notices", "activity_logs"},
        "admin": {"tenures", "members", "alumni", "events", "mentors", "certificates", "papers", "blogs",
                  "notices", "activity_logs"},
        "cms_user": {"tenures", "members", "alumni", "events", "mentors", "certificates", "papers", "blogs", "notices"},
        "operations": {"events", "mentors", "certificates", "papers", "notices"},
        "papers": {"papers"},
        "notice": {"notices"},
        "blog": {"blogs"},
    }

    def test_overview_modules_per_role(self):
        client = APIClient()
        for role, expected in self.EXPECTED.items():
            client.force_authenticate(make_user(role))
            modules = client.get("/api/v1/dashboard/overview/").data["modules"]
            self.assertEqual(set(modules), expected, role)

    @override_settings(DUPLICATE_REQUEST_WINDOW=5, CORS_ALLOWED_ORIGINS=[TRUSTED], CSRF_TRUSTED_ORIGINS=[TRUSTED])
    def test_identical_rapid_post_rejected(self):
        cache.clear()
        client = APIClient()
        login(client, make_user("notice"))
        body = {"title": "Once", "description": "d", "status": "draft"}
        first = client.post("/api/v1/notices/", body, format="json", HTTP_ORIGIN=TRUSTED)
        second = client.post("/api/v1/notices/", body, format="json", HTTP_ORIGIN=TRUSTED)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(Notice.objects.filter(title="Once").count(), 1)


# ----------------------------------------------------------------------------- S12
class UploadTypeValidationTests(TestCase):
    def test_active_content_uploads_rejected(self):
        client = APIClient()
        client.force_authenticate(make_user("operations"))
        bad = ContentFile(b"<script>alert(1)</script>", name="x.html")
        res = client.post("/api/v1/events/", {"title": "E", "description": "d", "date": timezone.now().isoformat(),
                                              "image": bad}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertIn("image", res.data)
        svg = ContentFile(b"<svg onload=alert(1)>", name="t.svg")
        res = client.post("/api/v1/certificates/templates/", {"template_name": "T", "template_file": svg},
                          format="multipart")
        self.assertEqual(res.status_code, 400)