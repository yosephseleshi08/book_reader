from django.urls import path
from .views import create_checkout, create_portal, stripe_webhook

urlpatterns = [
    path("checkout/", create_checkout, name="billing-checkout"),
    path("portal/", create_portal, name="billing-portal"),
    path("webhook/", stripe_webhook, name="billing-webhook"),
]
