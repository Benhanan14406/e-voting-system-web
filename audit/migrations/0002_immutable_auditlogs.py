from django.db import migrations

CREATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS prevent_auditlog_delete
BEFORE DELETE ON audit_auditlog
BEGIN
    SELECT RAISE(ABORT, 'Audit log entries are immutable and cannot be deleted.');
END;
"""

DROP_TRIGGER = """
DROP TRIGGER IF EXISTS prevent_auditlog_delete;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_TRIGGER,
            reverse_sql=DROP_TRIGGER,
        ),
    ]