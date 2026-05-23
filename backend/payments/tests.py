import uuid
from decimal import Decimal

from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from .models import LedgerEntry, Payment, PaymentStatus, PaymentWebhookLog, Wallet

PROCESSING = PaymentStatus.PROCESSING


def make_payment(wallet, amount_minor=1000, status=PaymentStatus.NEW):
    return Payment.objects.create(
        wallet=wallet,
        amount_minor=amount_minor,
        status=status,
    )


class FSMTests(TestCase):
    def setUp(self):
        self.wallet = Wallet.objects.get(id=1)

    def test_new_to_processing(self):
        p = make_payment(self.wallet)
        p.transition_to(PROCESSING)
        self.assertEqual(p.status, PROCESSING)

    def test_processing_to_succeeded(self):
        p = make_payment(self.wallet, status=PROCESSING)
        p.transition_to(PaymentStatus.SUCCEEDED)
        self.assertEqual(p.status, PaymentStatus.SUCCEEDED)

    def test_processing_to_failed(self):
        p = make_payment(self.wallet, status=PROCESSING)
        p.transition_to(PaymentStatus.FAILED)
        self.assertEqual(p.status, PaymentStatus.FAILED)

    def test_succeeded_is_terminal(self):
        p = make_payment(self.wallet, status=PaymentStatus.SUCCEEDED)
        with self.assertRaises(ValueError):
            p.transition_to(PaymentStatus.FAILED)

    def test_failed_is_terminal(self):
        p = make_payment(self.wallet, status=PaymentStatus.FAILED)
        with self.assertRaises(ValueError):
            p.transition_to(PaymentStatus.SUCCEEDED)

    def test_new_to_succeeded_forbidden(self):
        p = make_payment(self.wallet)
        with self.assertRaises(ValueError):
            p.transition_to(PaymentStatus.SUCCEEDED)

    def test_processing_to_new_forbidden(self):
        p = make_payment(self.wallet, status=PROCESSING)
        with self.assertRaises(ValueError):
            p.transition_to(PaymentStatus.NEW)


class AmountValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_valid_amount(self):
        resp = self.client.post(
            "/api/payments/",
            {"amount": "100.50"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        payment = Payment.objects.get(id=resp.data["id"])
        self.assertEqual(payment.amount_minor, Decimal("10050.00"))

    def test_valid_integer_amount(self):
        resp = self.client.post(
            "/api/payments/",
            {"amount": "500"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        payment = Payment.objects.get(id=resp.data["id"])
        self.assertEqual(payment.amount_minor, Decimal("50000"))

    def test_minimum_amount(self):
        resp = self.client.post(
            "/api/payments/",
            {"amount": "0.01"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_zero_rejected(self):
        resp = self.client.post(
            "/api/payments/",
            {"amount": "0"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_negative_rejected(self):
        resp = self.client.post(
            "/api/payments/",
            {"amount": "-10"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_three_decimal_places_rejected(self):
        resp = self.client.post(
            "/api/payments/",
            {"amount": "10.123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_exceeds_max_rejected(self):
        resp = self.client.post(
            "/api/payments/",
            {"amount": "10000001"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_non_numeric_rejected(self):
        resp = self.client.post(
            "/api/payments/",
            {"amount": "abc"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_missing_amount_rejected(self):
        resp = self.client.post("/api/payments/", {}, format="json")
        self.assertEqual(resp.status_code, 400)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=False,
)
class PaymentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_payment(self):
        resp = self.client.post(
            "/api/payments/",
            {"amount": "100.00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], PaymentStatus.NEW)
        self.assertEqual(resp.data["amount"], "100.00")

    def test_list_payments(self):
        wallet = Wallet.objects.get(id=1)
        before = Payment.objects.count()
        make_payment(wallet, 5000)
        make_payment(wallet, 10000)
        resp = self.client.get("/api/payments/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), before + 2)

    def test_wallet_balance_endpoint(self):
        resp = self.client.get("/api/wallet/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("balance", resp.data)


class WebhookSuccessTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.wallet = Wallet.objects.get_or_create(id=1)[0]
        self.wallet.refresh_from_db()
        self.initial_balance = self.wallet.balance_minor
        self.payment = make_payment(
            self.wallet,
            10050,
            status=PROCESSING,
        )

    def test_succeeded_webhook(self):
        event_id = str(uuid.uuid4())
        resp = self.client.post(
            "/api/webhooks/payment/",
            {
                "event_id": event_id,
                "payment_id": str(self.payment.id),
                "operator_payment_id": "op_123",
                "status": "succeeded",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(self.payment.operator_payment_id, "op_123")

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_minor, self.initial_balance + Decimal("10050"))

        entry = LedgerEntry.objects.get(
            payment=self.payment,
            status=PaymentStatus.SUCCEEDED,
        )
        self.assertEqual(entry.amount_minor, Decimal("10050"))

    def test_failed_webhook(self):
        resp = self.client.post(
            "/api/webhooks/payment/",
            {
                "event_id": str(uuid.uuid4()),
                "payment_id": str(self.payment.id),
                "operator_payment_id": "op_456",
                "status": "failed",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.FAILED)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_minor, self.initial_balance)

        entry = LedgerEntry.objects.get(
            payment=self.payment,
            status=PaymentStatus.FAILED,
        )
        self.assertEqual(entry.amount_minor, Decimal("10050"))


class WebhookIdempotencyTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.wallet = Wallet.objects.get_or_create(id=1)[0]
        self.wallet.refresh_from_db()
        self.initial_balance = self.wallet.balance_minor
        self.initial_succeeded = LedgerEntry.objects.filter(status=PaymentStatus.SUCCEEDED).count()
        self.initial_webhooks = PaymentWebhookLog.objects.count()
        self.payment = make_payment(
            self.wallet,
            5000,
            status=PROCESSING,
        )
        self.event_id = str(uuid.uuid4())

    def test_duplicate_webhook_ignored(self):
        payload = {
            "event_id": self.event_id,
            "payment_id": str(self.payment.id),
            "operator_payment_id": "op_789",
            "status": "succeeded",
        }
        resp1 = self.client.post(
            "/api/webhooks/payment/",
            payload,
            format="json",
        )
        self.assertEqual(resp1.status_code, 200)

        resp2 = self.client.post(
            "/api/webhooks/payment/",
            payload,
            format="json",
        )
        self.assertEqual(resp2.status_code, 200)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_minor, self.initial_balance + Decimal("5000"))
        self.assertEqual(
            LedgerEntry.objects.filter(status=PaymentStatus.SUCCEEDED).count(),
            self.initial_succeeded + 1,
        )
        self.assertEqual(PaymentWebhookLog.objects.count(), self.initial_webhooks + 1)

    def test_conflict_status_ignored(self):
        self.client.post(
            "/api/webhooks/payment/",
            {
                "event_id": str(uuid.uuid4()),
                "payment_id": str(self.payment.id),
                "operator_payment_id": "op_1",
                "status": "succeeded",
            },
            format="json",
        )

        self.client.post(
            "/api/webhooks/payment/",
            {
                "event_id": str(uuid.uuid4()),
                "payment_id": str(self.payment.id),
                "operator_payment_id": "op_2",
                "status": "failed",
            },
            format="json",
        )

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.SUCCEEDED)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_minor, self.initial_balance + Decimal("5000"))

    def test_webhook_nonexistent_payment(self):
        resp = self.client.post(
            "/api/webhooks/payment/",
            {
                "event_id": str(uuid.uuid4()),
                "payment_id": str(uuid.uuid4()),
                "operator_payment_id": "op_x",
                "status": "succeeded",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 404)


class MultiplePaymentsTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.wallet = Wallet.objects.get_or_create(id=1)[0]

    def test_balance_accumulates(self):
        self.wallet.refresh_from_db()
        initial_balance = self.wallet.balance_minor
        initial_ledger = LedgerEntry.objects.count()

        payments = [make_payment(self.wallet, amt, status=PROCESSING) for amt in (1000, 2000, 3000)]
        for p in payments:
            self.client.post(
                "/api/webhooks/payment/",
                {
                    "event_id": str(uuid.uuid4()),
                    "payment_id": str(p.id),
                    "operator_payment_id": f"op_{p.id}",
                    "status": "succeeded",
                },
                format="json",
            )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_minor, initial_balance + Decimal("6000"))
        self.assertEqual(LedgerEntry.objects.count(), initial_ledger + 3)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class WorkerIdempotencyTests(TransactionTestCase):
    def setUp(self):
        self.wallet = Wallet.objects.get_or_create(id=1)[0]

    def test_task_skips_non_new_payment(self):
        from .tasks import send_payment_to_operator

        payment = make_payment(
            self.wallet,
            1000,
            status=PROCESSING,
        )
        send_payment_to_operator(str(payment.id))
        payment.refresh_from_db()
        self.assertEqual(payment.status, PROCESSING)
