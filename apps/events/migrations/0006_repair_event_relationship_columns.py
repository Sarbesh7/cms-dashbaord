from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0005_repair_event_mentors_table"),
        ("tenure", "0004_alter_member_options_alter_tenure_options_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "events_event"
                    ADD COLUMN IF NOT EXISTS "tenure_id" bigint NULL;
                ALTER TABLE "events_mentor"
                    ADD COLUMN IF NOT EXISTS "member_id" bigint NULL;
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'events_event_tenure_id_8a7f2d1f_fk_tenure_tenure_id'
                    ) THEN
                        ALTER TABLE "events_event"
                            ADD CONSTRAINT "events_event_tenure_id_8a7f2d1f_fk_tenure_tenure_id"
                            FOREIGN KEY ("tenure_id") REFERENCES "tenure_tenure" ("id")
                            DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'events_mentor_member_id_1f22a0de_fk_tenure_member_id'
                    ) THEN
                        ALTER TABLE "events_mentor"
                            ADD CONSTRAINT "events_mentor_member_id_1f22a0de_fk_tenure_member_id"
                            FOREIGN KEY ("member_id") REFERENCES "tenure_member" ("id")
                            DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                END
                $$;
                CREATE INDEX IF NOT EXISTS "events_event_tenure_id_8a7f2d1f"
                    ON "events_event" ("tenure_id");
                CREATE INDEX IF NOT EXISTS "events_mentor_member_id_1f22a0de"
                    ON "events_mentor" ("member_id");
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
