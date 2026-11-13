from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0010_alter_event_options_alter_event_date_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DROP TABLE IF EXISTS "events_eventmentor" CASCADE;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
