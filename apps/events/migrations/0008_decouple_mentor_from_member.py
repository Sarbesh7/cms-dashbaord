from django.db import migrations, models
import django.db.models.deletion


def copy_member_data_into_mentors(apps, schema_editor):
    """Fill blank mentor fields from the linked member before the link is dropped."""
    Mentor = apps.get_model('events', 'Mentor')
    Member = apps.get_model('tenure', 'Member')
    mentors = list(Mentor.objects.filter(member__isnull=False))
    # Read only the columns needed; other Member columns may differ between databases.
    members = {
        row['id']: row
        for row in Member.objects.filter(pk__in=[m.member_id for m in mentors]).values('id', 'name', 'email', 'image')
    }
    for mentor in mentors:
        member = members.get(mentor.member_id)
        if not member:
            continue
        changed = []
        if not mentor.name and member['name']:
            mentor.name = member['name']
            changed.append('name')
        if not mentor.email and member['email']:
            mentor.email = member['email']
            changed.append('email')
        if not mentor.photo and member['image']:
            mentor.photo = member['image']
            changed.append('photo')
        if changed:
            mentor.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0007_alter_mentor_slug_eventmentorassignment_and_more'),
        ('tenure', '0004_alter_member_options_alter_tenure_options_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_member_data_into_mentors, reverse_code=migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='mentor',
            name='member',
        ),
        migrations.RemoveField(
            model_name='mentor',
            name='slug',
        ),
    ]
