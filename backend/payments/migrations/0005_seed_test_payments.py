import uuid

from django.db import migrations

SEED_PAYMENTS = [
    {"amount_minor": 10050, "status": "succeeded"},
    {"amount_minor": 50000, "status": "succeeded"},
    {"amount_minor": 250000, "status": "succeeded"},
    {"amount_minor": 75000, "status": "failed"},
    {"amount_minor": 30000, "status": "processing"},
]


def create_seed_data(apps, _schema_editor):
    Wallet = apps.get_model("payments", "Wallet")
    Payment = apps.get_model("payments", "Payment")
    LedgerEntry = apps.get_model("payments", "LedgerEntry")

    wallet = Wallet.objects.get(id=1)
    balance_increment = 0

    for spec in SEED_PAYMENTS:
        payment_id = uuid.uuid4()
        amount = spec["amount_minor"]
        final_status = spec["status"]

        payment = Payment.objects.create(
            id=payment_id,
            wallet=wallet,
            amount_minor=amount,
            status=final_status,
            idempotency_key=uuid.uuid4(),
        )

        statuses = ["new"]
        if final_status in ("processing", "succeeded", "failed"):
            statuses.append("processing")
        if final_status in ("succeeded", "failed"):
            statuses.append(final_status)

        for s in statuses:
            LedgerEntry.objects.create(
                wallet=wallet,
                payment=payment,
                amount_minor=amount,
                status=s,
            )

        if final_status == "succeeded":
            balance_increment += amount

    wallet.balance_minor += balance_increment
    wallet.save()


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0004_ledger_status"),
    ]

    operations = [
        migrations.RunPython(create_seed_data, migrations.RunPython.noop),
    ]
