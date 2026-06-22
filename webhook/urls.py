from django.urls import path
from .views import TradeWebhookView, DailySummaryView

urlpatterns = [
    path("trade/",   TradeWebhookView.as_view(),   name="trade-webhook"),
    path("summary/", DailySummaryView.as_view(),   name="daily-summary"),
]
