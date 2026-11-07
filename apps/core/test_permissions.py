from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from apps.core.permissions import (
    ROLES,
    has_role_permission,
    HasModulePermission,
    IsSuperadminOnly,
    CanViewActivityLogs,
)

User = get_user_model()


class PermissionCatalogTests(TestCase):
    def test_superadmin_has_all_permissions(self):
        self.assertTrue(has_role_permission("superadmin", "notices", "create"))
        self.assertTrue(has_role_permission("superadmin", "events", "delete"))
        self.assertTrue(has_role_permission("superadmin", "accounts", "manage"))
        self.assertTrue(has_role_permission("superadmin", "tenure", "member_delete"))
        self.assertTrue(has_role_permission("superadmin", "activity_logs", "view"))

    def test_admin_permissions_and_protected_restrictions(self):
        # Admin can view, create, edit tenure
        self.assertTrue(has_role_permission("admin", "tenure", "view"))
        self.assertTrue(has_role_permission("admin", "tenure", "create"))
        self.assertTrue(has_role_permission("admin", "tenure", "edit"))
        # Admin can access standard modules
        self.assertTrue(has_role_permission("admin", "events", "create"))
        self.assertTrue(has_role_permission("admin", "notices", "delete"))
        self.assertTrue(has_role_permission("admin", "blogs", "edit"))
        self.assertTrue(has_role_permission("admin", "activity_logs", "view"))

        # Protected restrictions: Admin CANNOT manage accounts or delete members
        self.assertFalse(has_role_permission("admin", "accounts", "manage"))
        self.assertFalse(has_role_permission("admin", "tenure", "member_delete"))

    def test_cms_user_permissions(self):
        # CMS User has events, notices, blogs, papers, certificates
        self.assertTrue(has_role_permission("cms_user", "events", "create"))
        self.assertTrue(has_role_permission("cms_user", "notices", "edit"))
        self.assertTrue(has_role_permission("cms_user", "blogs", "create"))
        self.assertTrue(has_role_permission("cms_user", "papers", "delete"))
        self.assertTrue(has_role_permission("cms_user", "certificates", "view"))

        # CMS User manages tenures, members and alumni
        self.assertTrue(has_role_permission("cms_user", "tenure", "view"))
        self.assertTrue(has_role_permission("cms_user", "tenure", "create"))
        # ...but member deletion stays superadmin-only
        self.assertFalse(has_role_permission("cms_user", "tenure", "member_delete"))

        # CMS user cannot access activity logs or account management
        self.assertFalse(has_role_permission("cms_user", "activity_logs", "view"))
        self.assertFalse(has_role_permission("cms_user", "accounts", "manage"))

    def test_operations_role_permissions(self):
        self.assertTrue(has_role_permission("operations", "events", "create"))
        self.assertTrue(has_role_permission("operations", "certificates", "create"))
        self.assertTrue(has_role_permission("operations", "papers", "create"))
        self.assertTrue(has_role_permission("operations", "notices", "create"))
        self.assertFalse(has_role_permission("operations", "blogs", "create"))
        self.assertFalse(has_role_permission("operations", "tenure", "view"))
        self.assertFalse(has_role_permission("operations", "activity_logs", "view"))

    def test_papers_role_permissions(self):
        self.assertTrue(has_role_permission("papers", "papers", "create"))
        self.assertTrue(has_role_permission("papers", "papers", "delete"))
        self.assertFalse(has_role_permission("papers", "events", "create"))
        self.assertFalse(has_role_permission("papers", "blogs", "create"))

    def test_notice_role_permissions(self):
        self.assertTrue(has_role_permission("notice", "notices", "create"))
        self.assertTrue(has_role_permission("notice", "notices", "edit"))
        self.assertFalse(has_role_permission("notice", "events", "create"))
        self.assertFalse(has_role_permission("notice", "papers", "create"))

    def test_blog_role_permissions(self):
        self.assertTrue(has_role_permission("blog", "blogs", "create"))
        self.assertTrue(has_role_permission("blog", "blogs", "publish"))
        self.assertFalse(has_role_permission("blog", "notices", "create"))
        self.assertFalse(has_role_permission("blog", "events", "create"))

    def test_invalid_role(self):
        self.assertFalse(has_role_permission("random_role", "events", "view"))

    def test_notification_role_permissions(self):
        # Superadmin, Admin, and CMS User have equal notifications access
        for role in ("superadmin", "admin", "cms_user"):
            self.assertTrue(has_role_permission(role, "notifications", "view"), f"{role} should have notifications.view")
            self.assertTrue(has_role_permission(role, "notifications", "send"), f"{role} should have notifications.send")

        # Other roles have no notifications access
        for role in ("operations", "papers", "notice", "blog"):
            self.assertFalse(has_role_permission(role, "notifications", "view"), f"{role} should NOT have notifications.view")
            self.assertFalse(has_role_permission(role, "notifications", "send"), f"{role} should NOT have notifications.send")
            self.assertFalse(has_role_permission(role, "notifications", "retry"), f"{role} should NOT have notifications.retry")


class DRFPermissionClassesTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.superadmin = User.objects.create_user(
            username="superadmin", email="superadmin@test.com", password="password123", role="superadmin"
        )
        self.admin = User.objects.create_user(
            username="admin", email="admin@test.com", password="password123", role="admin"
        )
        self.blog_user = User.objects.create_user(
            username="blogger", email="blogger@test.com", password="password123", role="blog"
        )

    def test_has_module_permission_class(self):
        class DummyBlogView(APIView):
            permission_module = "blogs"

        view = DummyBlogView.as_view()
        perm = HasModulePermission()

        # Blog user POST to blogs -> allowed
        request = self.factory.post("/api/v1/blogs/")
        request.user = self.blog_user
        self.assertTrue(perm.has_permission(request, DummyBlogView()))

        # Blog user POST to events -> denied
        class DummyEventView(APIView):
            permission_module = "events"

        request = self.factory.post("/api/v1/events/")
        request.user = self.blog_user
        self.assertFalse(perm.has_permission(request, DummyEventView()))

    def test_is_superadmin_only_class(self):
        perm = IsSuperadminOnly()
        request = self.factory.get("/api/v1/users/accounts/")

        request.user = self.superadmin
        self.assertTrue(perm.has_permission(request, None))

        request.user = self.admin
        self.assertFalse(perm.has_permission(request, None))

    def test_can_view_activity_logs_class(self):
        perm = CanViewActivityLogs()
        request = self.factory.get("/api/v1/activity-logs/")

        request.user = self.superadmin
        self.assertTrue(perm.has_permission(request, None))

        request.user = self.admin
        self.assertTrue(perm.has_permission(request, None))

        request.user = self.blog_user
        self.assertFalse(perm.has_permission(request, None))
