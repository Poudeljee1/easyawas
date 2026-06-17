from django.urls import path
from .views import TradeWebhookView

urlpatterns = [
    path("trade/", TradeWebhookView.as_view(), name="trade-webhook"),
]
