import uuid

from django.db import models


class PaymentStatus(models.TextChoices):
    NEW = "new"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


ALLOWED_TRANSITIONS = {
    PaymentStatus.NEW: {PaymentStatus.PROCESSING},
    PaymentStatus.PROCESSING: {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED},
}


class Wallet(models.Model):
    balance_minor = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="payments")
    amount_minor = models.BigIntegerField()
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.NEW
    )
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True)
    operator_payment_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def can_transition_to(self, new_status):
        return new_status in ALLOWED_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status):
        if not self.can_transition_to(new_status):
            msg = f"Cannot transition from {self.status} to {new_status}"
            raise ValueError(msg)
        self.status = new_status


class LedgerEntry(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="ledger_entries")
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="ledger_entry")
    amount_minor = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentWebhookLog(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="webhook_logs")
    event_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20)
    body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
