from django.db import IntegrityError, transaction
from django.db.models import F
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LedgerEntry, Payment, PaymentStatus, PaymentWebhookLog, Wallet
from .serializers import (
    CreatePaymentSerializer,
    PaymentSerializer,
    WalletSerializer,
    WebhookSerializer,
)
from .tasks import send_payment_to_operator


class WalletView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer

    def get_object(self):
        wallet, _ = Wallet.objects.get_or_create(id=1)
        return wallet


class PaymentListCreateView(generics.ListCreateAPIView):
    queryset = Payment.objects.all()[:20]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreatePaymentSerializer
        return PaymentSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.method == "POST":
            wallet, _ = Wallet.objects.get_or_create(id=1)
            ctx["wallet"] = wallet
        return ctx

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        send_payment_to_operator.delay(str(payment.id))
        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


class WebhookView(APIView):
    def post(self, request):
        serializer = WebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        new_status = (
            PaymentStatus.SUCCEEDED if data["status"] == "succeeded" else PaymentStatus.FAILED
        )

        try:
            with transaction.atomic():
                try:
                    PaymentWebhookLog.objects.create(
                        payment_id=data["payment_id"],
                        event_id=data["event_id"],
                        status=data["status"],
                        body=request.data,
                    )
                except IntegrityError:
                    return Response(status=status.HTTP_200_OK)

                payment = Payment.objects.select_for_update().get(id=data["payment_id"])

                if not payment.can_transition_to(new_status):
                    return Response(status=status.HTTP_200_OK)

                payment.transition_to(new_status)
                payment.operator_payment_id = data["operator_payment_id"]
                payment.save()

                if new_status == PaymentStatus.SUCCEEDED:
                    LedgerEntry.objects.create(
                        wallet=payment.wallet,
                        payment=payment,
                        amount_minor=payment.amount_minor,
                    )
                    Wallet.objects.filter(
                        id=payment.wallet_id,
                    ).update(
                        balance_minor=F("balance_minor") + payment.amount_minor,
                    )
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(status=status.HTTP_200_OK)
