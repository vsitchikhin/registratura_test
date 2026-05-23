from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from .models import LedgerEntry, Payment, PaymentStatus, Wallet

MIN_AMOUNT = Decimal("0.01")
MAX_AMOUNT = Decimal("10000000.00")


def minor_to_str(amount_minor):
    return str((amount_minor / 100).quantize(Decimal("0.01")))


class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ["balance"]

    def get_balance(self, obj):
        return minor_to_str(obj.balance_minor)


class AmountField(serializers.CharField):
    def to_internal_value(self, data):
        raw = super().to_internal_value(data)
        try:
            amount = Decimal(raw)
        except InvalidOperation as e:
            raise serializers.ValidationError("Некорректная сумма.") from e
        if amount < MIN_AMOUNT:
            raise serializers.ValidationError(f"Минимальная сумма: {MIN_AMOUNT} RUB.")
        if amount > MAX_AMOUNT:
            raise serializers.ValidationError(f"Максимальная сумма: {MAX_AMOUNT} RUB.")
        if amount.as_tuple().exponent < -2:
            raise serializers.ValidationError("Максимум 2 знака после запятой.")
        return amount * 100


class CreatePaymentSerializer(serializers.Serializer):
    amount = AmountField()

    def create(self, validated_data):
        wallet = self.context["wallet"]
        payment = Payment.objects.create(
            wallet=wallet,
            amount_minor=validated_data["amount"],
        )
        LedgerEntry.objects.create(
            wallet=wallet,
            payment=payment,
            amount_minor=payment.amount_minor,
            status=PaymentStatus.NEW,
        )
        return payment


class PaymentSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ["id", "amount", "status", "created_at"]

    def get_amount(self, obj):
        return minor_to_str(obj.amount_minor)


class WebhookSerializer(serializers.Serializer):
    event_id = serializers.CharField()
    payment_id = serializers.UUIDField()
    operator_payment_id = serializers.CharField()
    status = serializers.ChoiceField(choices=["succeeded", "failed"])
