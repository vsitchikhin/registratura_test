import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction

from .models import LedgerEntry, Payment, PaymentStatus


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def send_payment_to_operator(self, payment_id):
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment_id)
        if payment.status != PaymentStatus.NEW:
            return
        payment.transition_to(PaymentStatus.PROCESSING)
        payment.save()
        LedgerEntry.objects.create(
            wallet=payment.wallet,
            payment=payment,
            amount_minor=payment.amount_minor,
            status=PaymentStatus.PROCESSING,
        )

    try:
        requests.post(
            settings.PAYMENT_OPERATOR_URL,
            json={
                "payment_id": str(payment.id),
                "amount_minor": str(payment.amount_minor),
                "currency": "RUB",
                "idempotency_key": str(payment.idempotency_key),
                "webhook_url": f"{settings.WEBHOOK_BASE_URL}/api/webhooks/payment/",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise self.retry(exc=exc) from exc
