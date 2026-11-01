from django.db import migrations, models


def copy_uploaded_featured_images(apps, schema_editor):
    """Preserve previously uploaded featured images as URL + storage reference."""
    Blog = apps.get_model('blogs', 'Blog')
    for blog in Blog.objects.exclude(featured_image='').exclude(featured_image__isnull=True):
        try:
            url = blog.featured_image.url
        except Exception:
            continue
        if not url.startswith(('http://', 'https://')):
            # Local FileSystemStorage returns a relative /media/ path; keep the reference only
            if not blog.featured_image_url:
                blog.featured_image_public_id = blog.featured_image.name
                blog.save(update_fields=['featured_image_public_id'])
            continue
        blog.featured_image_url = url
        blog.featured_image_public_id = blog.featured_image.name
        blog.save(update_fields=['featured_image_url', 'featured_image_public_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('blogs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='blog',
            name='featured_image_public_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.RunPython(copy_uploaded_featured_images, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='blog',
            name='featured_image',
        ),
        migrations.AddField(
            model_name='blog',
            name='content_images',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='blog',
            name='seo_title',
            field=models.CharField(blank=True, default='', max_length=70),
        ),
        migrations.AddField(
            model_name='blog',
            name='seo_description',
            field=models.CharField(blank=True, default='', max_length=160),
        ),
        migrations.AlterField(
            model_name='blog',
            name='excerpt',
            field=models.TextField(blank=True, default='', max_length=300),
        ),
        migrations.AlterField(
            model_name='blog',
            name='status',
            field=models.CharField(choices=[('draft', 'Draft'), ('published', 'Published')], db_index=True, default='draft', max_length=20),
        ),
    ]
