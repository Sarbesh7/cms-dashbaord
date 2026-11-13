from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from apps.papers.models import PastPaper

User = get_user_model()


class PastPaperIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpassword123",
            role="admin",
        )
        self.client.force_authenticate(user=self.user)

        # Create new course paper
        self.paper_new = PastPaper.objects.create(
            subject_name="CSC115",  # C Programming
            semester=1,
            exam_year=2080,
            model_set=False,
            drive_link="https://drive.google.com/file/d/test1/view",
            is_old_course=False,
        )

        # Create old course paper with same subject code
        self.paper_old = PastPaper.objects.create(
            subject_name="CSC115",
            semester=1,
            exam_year=2080,
            model_set=False,
            drive_link="https://drive.google.com/file/d/test2/view",
            is_old_course=True,
        )

    def test_past_paper_creation_and_old_course_field(self):
        """Verify past papers support is_old_course and custom codes."""
        self.assertFalse(self.paper_new.is_old_course)
        self.assertTrue(self.paper_old.is_old_course)
        self.assertNotEqual(self.paper_new.slug, self.paper_old.slug)
        self.assertIn("old", self.paper_old.slug)

    def test_search_by_human_readable_name(self):
        """Searching for 'Programming' matches CSC115 (C Programming)."""
        response = self.client.get("/api/v1/past-papers/?search=Programming")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return both papers
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_filter_by_is_old_course(self):
        """Filtering by is_old_course=true returns only old course papers."""
        response = self.client.get("/api/v1/past-papers/?is_old_course=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.paper_old.id)

        response_new = self.client.get("/api/v1/past-papers/?is_old_course=false")
        self.assertEqual(response_new.status_code, status.HTTP_200_OK)
        self.assertEqual(response_new.data["count"], 1)
        self.assertEqual(response_new.data["results"][0]["id"], self.paper_new.id)

    def test_past_paper_numeric_slug_lookup_and_delete(self):
        """Verify past paper with numeric slug (e.g. '5555') resolves and deletes."""
        paper = PastPaper.objects.create(
            subject_name="MTH117",
            semester=1,
            exam_year=2081,
            drive_link="https://drive.google.com/file/d/test3/view",
        )
        PastPaper.objects.filter(id=paper.id).update(slug="5555")
        paper.refresh_from_db()
        self.assertEqual(paper.slug, "5555")
        self.assertNotEqual(paper.id, 5555)

        # GET detail using numeric slug
        resp = self.client.get("/api/v1/past-papers/5555/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], paper.id)

        # DELETE using numeric slug
        del_resp = self.client.delete("/api/v1/past-papers/5555/")
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PastPaper.objects.filter(id=paper.id).exists())
