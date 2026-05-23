from django.db import migrations


def create_wallet(apps, _schema_editor):
    apps.get_model("payments", "Wallet").objects.get_or_create(id=1)


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_wallet, migrations.RunPython.noop),
    ]
