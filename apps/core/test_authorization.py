from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from apps.notices.models import Notice
from apps.events.models import Event
from apps.tenure.models import Member
from apps.certificates.models import Certificate
from apps.papers.models import PastPaper
from apps.blogs.models import Blog
from django.utils import timezone

User = get_user_model()


class ModuleAuthorizationIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users across different roles
        self.superadmin = User.objects.create_user(
            username="superadmin", email="superadmin@test.com", password="pass", role="superadmin"
        )
        self.admin = User.objects.create_user(
            username="admin", email="admin@test.com", password="pass", role="admin"
        )
        self.cms_user = User.objects.create_user(
            username="cms_user", email="cms@test.com", password="pass", role="cms_user"
        )
        self.notice_user = User.objects.create_user(
            username="notice_user", email="notice@test.com", password="pass", role="notice"
        )
        self.operations_user = User.objects.create_user(
            username="operations_user", email="ops@test.com", password="pass", role="operations"
        )
        self.papers_user = User.objects.create_user(
            username="papers_user", email="papers@test.com", password="pass", role="papers"
        )
        self.blog_user = User.objects.create_user(
            username="blog_user", email="blog@test.com", password="pass", role="blog"
        )

    def test_unauthenticated_mutations_receive_401(self):
        self.client.force_authenticate(user=None)

        # Notices
        res = self.client.post("/api/v1/notices/", {"title": "Test"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Events
        res = self.client.post("/api/v1/events/", {"title": "Test"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Members
        res = self.client.post("/api/v1/members/", {"name": "Test"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Papers
        res = self.client.post("/api/v1/past-papers/", {"subject_name": "CSIT101"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Blogs
        res = self.client.post("/api/v1/blogs/", {"title": "Test"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_role_based_access_matrix(self):
        # 1. Notice user can create notice, but CANNOT create events, blogs, papers
        self.client.force_authenticate(user=self.notice_user)
        res = self.client.post("/api/v1/events/", {"title": "Forbidden Event"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.post("/api/v1/blogs/", {"title": "Forbidden Blog"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.post("/api/v1/past-papers/", {"subject_name": "CSIT101"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Operations user can manage events and notices, but CANNOT create blogs
        self.client.force_authenticate(user=self.operations_user)
        res = self.client.post("/api/v1/blogs/", {"title": "Forbidden Blog"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.post("/api/v1/notices/", {"title": "Allowed Notice"})
        self.assertNotEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Blog user can create blogs, but CANNOT create events or notices
        self.client.force_authenticate(user=self.blog_user)
        res = self.client.post("/api/v1/events/", {"title": "Forbidden Event"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.post("/api/v1/notices/", {"title": "Forbidden Notice"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Papers user can create papers, but CANNOT create events
        self.client.force_authenticate(user=self.papers_user)
        res = self.client.post("/api/v1/events/", {"title": "Forbidden Event"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_delete_restriction(self):
        member = Member.objects.create(name="Jane Doe", email="jane@test.com", slug="jane-doe")

        # Admin CANNOT delete member (restricted to superadmin)
        self.client.force_authenticate(user=self.admin)
        res = self.client.delete(f"/api/v1/members/{member.slug}/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Only Superadmin can delete members", str(res.data))

        # CMS user CANNOT delete member
        self.client.force_authenticate(user=self.cms_user)
        res = self.client.delete(f"/api/v1/members/{member.slug}/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Superadmin CAN delete member
        self.client.force_authenticate(user=self.superadmin)
        res = self.client.delete(f"/api/v1/members/{member.slug}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Member.objects.filter(slug="jane-doe").exists())
