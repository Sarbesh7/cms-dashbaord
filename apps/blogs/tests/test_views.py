import io
import shutil
import tempfile
from datetime import date
from PIL import Image
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
from apps.blogs.models import Blog
from apps.tenure.models import Member, Tenure, TenureMembership

User = get_user_model()


def generate_test_image(name="test_image.jpg", fmt="jpeg"):
    file = io.BytesIO()
    Image.new('RGB', (100, 100), 'white').save(file, fmt)
    file.seek(0)
    return SimpleUploadedFile(name, file.read(), content_type=f"image/{fmt}")


class BlogAPITest(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="adminuser", password="password123", role="admin", is_staff=True
        )
        self.cms_user = User.objects.create_user(
            username="cmsuser", password="password123", role="cms_user"
        )

        # Members from a past and the current tenure: both are valid authors
        past = Tenure.objects.create(name="2022", start_date=date(2022, 1, 1), end_date=date(2022, 12, 31))
        current = Tenure.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        self.past_member = Member.objects.create(name="Past Writer", email="past@example.com")
        self.current_member = Member.objects.create(name="Current Writer", email="current@example.com")
        TenureMembership.objects.create(member=self.past_member, tenure=past, designation="Secretary")
        TenureMembership.objects.create(member=self.current_member, tenure=current, designation="President")

        self.blog1 = Blog.objects.create(
            title="Introduction to React",
            excerpt="A guide to React fundamentals",
            content="## React\nComponent based architecture.",
            status="published"
        )
        self.blog2 = Blog.objects.create(
            title="Draft Ideas for Next.js",
            excerpt="Draft post",
            content="Draft notes",
            status="draft"
        )

    def test_anonymous_cannot_read_management_endpoints(self):
        self.assertEqual(self.client.get('/api/v1/blogs/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.get(f'/api/v1/blogs/{self.blog2.id}/').status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_list_search_filter_and_pagination(self):
        self.client.force_authenticate(user=self.cms_user)
        res = self.client.get('/api/v1/blogs/?page_size=1')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)
        self.assertEqual(len(res.data['results']), 1)
        self.assertNotIn('content', res.data['results'][0])

        res = self.client.get('/api/v1/blogs/?search=React')
        self.assertEqual([b['title'] for b in res.data['results']], ["Introduction to React"])

        res = self.client.get('/api/v1/blogs/?status=draft')
        self.assertEqual([b['slug'] for b in res.data['results']], ["draft-ideas-for-nextjs"])

        reference = f"ART-{self.blog2.id:04d}"
        res = self.client.get(f'/api/v1/blogs/?search={reference.lower()}')
        self.assertEqual([b['reference'] for b in res.data['results']], [reference])

        res = self.client.get('/api/v1/blogs/?status=bogus')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_includes_content_and_seo(self):
        self.client.force_authenticate(user=self.cms_user)
        res = self.client.get(f'/api/v1/blogs/{self.blog1.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['content'], "## React\nComponent based architecture.")
        self.assertEqual(res.data['seo']['title'], "Introduction to React")
        self.assertEqual(res.data['seo']['description'], "A guide to React fundamentals")
        self.assertEqual(res.data['seo']['path'], "/blogs/introduction-to-react")

    def test_create_defaults_to_draft_and_tracks_images(self):
        res_anon = self.client.post('/api/v1/blogs/', {"title": "X", "content": "Y"}, format='json')
        self.assertEqual(res_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.cms_user)
        image_url = "https://res.cloudinary.com/demo/image/upload/blogs/content/a.jpg"
        payload = {
            "title": "Introduction to React",
            "content": f"Intro\n\n![Diagram]({image_url})\n",
            "content_images": [
                {"url": image_url, "public_id": "blogs/content/a", "alt": "Diagram"},
                {"url": "https://example.com/removed.jpg", "public_id": "gone"},
            ],
            "featured_image_url": "https://example.com/cover.jpg",
            "featured_image_public_id": "",
            "featured_image_alt": "Cover",
        }
        res = self.client.post('/api/v1/blogs/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['status'], "draft")
        self.assertIsNone(res.data['published_at'])
        self.assertEqual(res.data['slug'], "introduction-to-react-2")
        self.assertEqual([i['public_id'] for i in res.data['content_images']], ["blogs/content/a"])
        self.assertEqual(res.data['seo']['og_image'], "https://example.com/cover.jpg")

    def test_client_supplied_slug_and_seo_are_ignored(self):
        self.client.force_authenticate(user=self.cms_user)
        res = self.client.post(
            '/api/v1/blogs/',
            {"title": "Other Post", "slug": self.blog1.slug, "seo_title": "Hacked", "content": "Body text"},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['slug'], "other-post")
        self.assertEqual(res.data['seo']['title'], "Other Post")
        # No excerpt -> plain-text content fallback
        self.assertEqual(res.data['seo']['description'], "Body text")

    def test_unsafe_content_rejected(self):
        self.client.force_authenticate(user=self.cms_user)
        unsafe_bodies = [
            "Safe intro <script>alert('hack');</script>",
            "<img src=x onerror=alert(1)>",
            "[click](javascript:alert(1))",
            "[click](javascript&#58;alert(1))",
            "![pixel](data:image/png;base64,AAAA)",
            "<javascript:alert(1)>",
        ]
        for body in unsafe_bodies:
            res = self.client.post('/api/v1/blogs/', {"title": "Bad", "content": body}, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, body)
            self.assertIn('content', res.data)

        ok = self.client.post(
            '/api/v1/blogs/',
            {"title": "Ok", "content": "Use `<script>` tags carefully, <u>really</u>.\n\n"
                                       "[Docs](/docs) <https://example.com> <team@example.com>"},
            format='json',
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED, ok.data)

    def test_featured_image_url_must_be_http(self):
        self.client.force_authenticate(user=self.cms_user)
        res = self.client.post(
            '/api/v1/blogs/',
            {"title": "Bad cover", "content": "x", "featured_image_url": "data:image/png;base64,AAAA"},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_keeps_published_at_and_regenerates_slug(self):
        self.client.force_authenticate(user=self.cms_user)
        original = self.blog1.published_at
        res = self.client.put(
            f'/api/v1/blogs/{self.blog1.id}/',
            {"title": "Introduction to React 19", "content": "Updated content", "status": "published",
             "author_id": self.current_member.id},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.blog1.refresh_from_db()
        self.assertEqual(self.blog1.published_at, original)
        self.assertEqual(self.blog1.slug, "introduction-to-react-19")

    def test_publishing_requires_author(self):
        self.client.force_authenticate(user=self.cms_user)
        base = {"title": "Authored Post", "content": "Body"}

        # Drafts can be saved without an author
        draft = self.client.post('/api/v1/blogs/', {**base, "status": "draft"}, format='json')
        self.assertEqual(draft.status_code, status.HTTP_201_CREATED, draft.data)
        self.assertIsNone(draft.data['author'])

        # Publishing without an author is rejected by the backend
        res = self.client.patch(f'/api/v1/blogs/{draft.data["id"]}/', {"status": "published"}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('author_id', res.data)

        # Members from any tenure can be credited
        res = self.client.patch(
            f'/api/v1/blogs/{draft.data["id"]}/',
            {"status": "published", "author_id": self.past_member.id},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data['author']['name'], "Past Writer")
        self.assertEqual(res.data['seo']['author'], "Past Writer")

        res = self.client.patch(
            f'/api/v1/blogs/{draft.data["id"]}/', {"author_id": self.current_member.id}, format='json'
        )
        self.assertEqual(res.data['author']['id'], self.current_member.id)

        # Removing the author from a published article is rejected; unknown members too
        res = self.client.patch(f'/api/v1/blogs/{draft.data["id"]}/', {"author_id": None}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        res = self.client.patch(f'/api/v1/blogs/{draft.data["id"]}/', {"author_id": 99999}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        listing = self.client.get('/api/v1/blogs/?search=Authored')
        self.assertEqual(listing.data['results'][0]['author']['name'], "Current Writer")

    def test_deleting_member_keeps_blog(self):
        blog = Blog.objects.create(title="Kept", content="x", author=self.past_member, status="published")
        self.past_member.delete()
        blog.refresh_from_db()
        self.assertIsNone(blog.author)

    def test_saving_draft_does_not_publish(self):
        self.client.force_authenticate(user=self.cms_user)
        res = self.client.patch(f'/api/v1/blogs/{self.blog2.id}/', {"content": "More notes"}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], "draft")
        self.assertIsNone(res.data['published_at'])

        res = self.client.patch(f'/api/v1/blogs/{self.blog2.id}/', {"status": "archived"}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_removing_featured_image_clears_reference(self):
        self.client.force_authenticate(user=self.cms_user)
        self.blog2.featured_image_url = "https://example.com/x.jpg"
        self.blog2.featured_image_public_id = "blogs/content/x"
        self.blog2.save()
        res = self.client.patch(f'/api/v1/blogs/{self.blog2.id}/', {"featured_image_url": None}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data['featured_image_url'])
        self.assertEqual(res.data['featured_image_public_id'], "")

    def test_delete_requires_admin(self):
        self.client.force_authenticate(user=self.cms_user)
        self.assertEqual(
            self.client.delete(f'/api/v1/blogs/{self.blog2.id}/').status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(user=self.admin_user)
        self.assertEqual(
            self.client.delete(f'/api/v1/blogs/{self.blog2.id}/').status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(Blog.objects.filter(id=self.blog2.id).exists())

    def test_image_upload_endpoint(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media_root)
        override.enable()
        self.addCleanup(override.disable)

        self.client.force_authenticate(user=self.cms_user)
        res = self.client.post('/api/v1/blogs/upload-image/', {'image': generate_test_image()}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['url'].startswith('http'))
        self.assertTrue(res.data['public_id'].startswith('blogs/content/'))

        mismatched = generate_test_image(name="fake.png", fmt="jpeg")
        res = self.client.post('/api/v1/blogs/upload-image/', {'image': mismatched}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_image_delete_endpoint_success(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media_root)
        override.enable()
        self.addCleanup(override.disable)

        self.client.force_authenticate(user=self.cms_user)
        upload_res = self.client.post('/api/v1/blogs/upload-image/', {'image': generate_test_image()}, format='multipart')
        self.assertEqual(upload_res.status_code, status.HTTP_201_CREATED)
        pub_id = upload_res.data['public_id']
        url = upload_res.data['url']

        del_res = self.client.post('/api/v1/blogs/delete-image/', {'public_id': pub_id, 'url': url})
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)

    def test_image_delete_endpoint_conflict_when_referenced(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media_root)
        override.enable()
        self.addCleanup(override.disable)

        self.client.force_authenticate(user=self.cms_user)
        upload_res = self.client.post('/api/v1/blogs/upload-image/', {'image': generate_test_image()}, format='multipart')
        pub_id = upload_res.data['public_id']
        url = upload_res.data['url']

        # Create blog referencing this image
        Blog.objects.create(
            title="Shared Image Blog",
            slug="shared-image-blog",
            author=self.current_member,
            featured_image_url=url,
            content="Some text",
        )

        del_res = self.client.post('/api/v1/blogs/delete-image/', {'public_id': pub_id, 'url': url})
        self.assertEqual(del_res.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("referenced by other content", del_res.data['detail'])

    def test_blog_numeric_slug_lookup_and_delete(self):
        """Verify blog with numeric slug (e.g. '1234') resolves and deletes."""
        blog = Blog.objects.create(
            title="Numeric Blog",
            slug="1234",
            excerpt="Excerpt",
            content="Content",
            status="published"
        )
        self.assertNotEqual(blog.id, 1234)

        self.client.force_authenticate(user=self.admin_user)
        # GET detail using numeric slug
        resp = self.client.get("/api/v1/blogs/1234/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], blog.id)

        # DELETE using numeric slug
        del_resp = self.client.delete("/api/v1/blogs/1234/")
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Blog.objects.filter(id=blog.id).exists())

