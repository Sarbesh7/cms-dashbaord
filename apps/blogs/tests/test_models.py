from django.test import TestCase
from apps.blogs.models import Blog


class BlogModelTest(TestCase):
    def test_automatic_slug_generation(self):
        blog = Blog.objects.create(
            title="Getting Started with Python",
            content="# Hello World"
        )
        self.assertEqual(blog.slug, "getting-started-with-python")
        self.assertEqual(blog.status, "draft")
        self.assertIsNone(blog.published_at)

    def test_slug_collision_resolution(self):
        blog1 = Blog.objects.create(title="Getting Started", content="Post 1")
        blog2 = Blog.objects.create(title="Getting Started", content="Post 2")
        blog3 = Blog.objects.create(title="Getting Started", content="Post 3")

        self.assertEqual(blog1.slug, "getting-started")
        self.assertEqual(blog2.slug, "getting-started-2")
        self.assertEqual(blog3.slug, "getting-started-3")

    def test_slug_regenerates_uniquely_on_title_change(self):
        Blog.objects.create(title="Taken Title", content="x")
        blog = Blog.objects.create(title="Initial Title", content="Content here")

        blog.title = "Taken Title"
        blog.save()
        blog.refresh_from_db()
        self.assertEqual(blog.slug, "taken-title-2")

        # Saving without a title change keeps the slug
        blog.content = "Edited"
        blog.save()
        blog.refresh_from_db()
        self.assertEqual(blog.slug, "taken-title-2")

    def test_publication_date_preserved(self):
        blog = Blog.objects.create(title="Draft to Published", content="Article text")
        self.assertIsNone(blog.published_at)

        blog.status = "published"
        blog.save()
        initial_published_at = blog.published_at
        self.assertIsNotNone(initial_published_at)

        blog.content = "Updated article text"
        blog.save()
        blog.refresh_from_db()
        self.assertEqual(blog.published_at, initial_published_at)

        # Unpublishing keeps the original date; re-publishing does not reset it
        blog.status = "draft"
        blog.save()
        blog.status = "published"
        blog.save()
        blog.refresh_from_db()
        self.assertEqual(blog.published_at, initial_published_at)

    def test_published_queryset_excludes_drafts(self):
        Blog.objects.create(title="Live", content="x", status="published")
        Blog.objects.create(title="Hidden", content="x")
        self.assertEqual(list(Blog.objects.published().values_list('title', flat=True)), ["Live"])

    def test_seo_values_derived_from_fields(self):
        blog = Blog.objects.create(
            title="SEO Test Article",
            excerpt="This is a concise excerpt.",
            content="Long article body text...",
            featured_image_url="https://example.com/banner.jpg"
        )
        self.assertEqual(blog.seo_title, "SEO Test Article")
        self.assertEqual(blog.og_title, "SEO Test Article")
        self.assertEqual(blog.seo_description, "This is a concise excerpt.")
        self.assertEqual(blog.og_description, "This is a concise excerpt.")
        self.assertEqual(blog.og_image_url, "https://example.com/banner.jpg")

    def test_description_falls_back_to_plain_text_content(self):
        blog = Blog(title="T", content="## Heading\n\nSome **bold** and a [link](https://x.com).\n\n<u>under</u>")
        self.assertEqual(blog.seo_description, "Heading Some bold and a link. under")

        blog.content = "word " * 100
        self.assertLessEqual(len(blog.seo_description), 160)
        self.assertTrue(blog.seo_description.endswith("…"))
