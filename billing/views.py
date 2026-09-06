import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .stripe_utils import create_checkout_session, create_billing_portal_session
from accounts.models import Profile


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout(request):
    price_id = request.data.get("price_id", settings.STRIPE_PRICE_ID_PRO)
    success_url = request.data.get("success_url", "https://example.com/billing/success")
    cancel_url = request.data.get("cancel_url", "https://example.com/billing/cancel")

    session = create_checkout_session(request.user, price_id, success_url, cancel_url)
    return Response({"checkout_url": session.url})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_portal(request):
    return_url = request.data.get("return_url", "https://example.com/account")
    session = create_billing_portal_session(request.user, return_url)
    return Response({"portal_url": session.url})


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _activate_subscription(data.get("customer"), data.get("subscription"))

    elif event_type == "customer.subscription.updated":
        _sync_subscription_status(data)

    elif event_type == "customer.subscription.deleted":
        _deactivate_subscription(data.get("customer"))

    return HttpResponse(status=200)


def _activate_subscription(customer_id, subscription_id):
    try:
        profile = Profile.objects.get(stripe_customer_id=customer_id)
    except Profile.DoesNotExist:
        return
    profile.stripe_subscription_id = subscription_id or ""
    profile.subscription_active = True
    profile.plan = "pro"
    profile.save(update_fields=["stripe_subscription_id", "subscription_active", "plan"])


def _sync_subscription_status(subscription_obj):
    customer_id = subscription_obj.get("customer")
    status_value = subscription_obj.get("status")
    try:
        profile = Profile.objects.get(stripe_customer_id=customer_id)
    except Profile.DoesNotExist:
        return
    profile.subscription_active = status_value in ("active", "trialing")
    profile.save(update_fields=["subscription_active"])


def _deactivate_subscription(customer_id):
    try:
        profile = Profile.objects.get(stripe_customer_id=customer_id)
    except Profile.DoesNotExist:
        return
    profile.subscription_active = False
    profile.plan = "free"
    profile.save(update_fields=["subscription_active", "plan"])
