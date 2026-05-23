from django.urls import path

from payments.views import PaymentListCreateView, WalletView, WebhookView

urlpatterns = [
    path("api/wallet/", WalletView.as_view()),
    path("api/payments/", PaymentListCreateView.as_view()),
    path("api/webhooks/payment/", WebhookView.as_view()),
]
