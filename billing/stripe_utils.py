import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def get_or_create_customer(user) -> str:
    profile = user.profile
    if profile.stripe_customer_id:
        return profile.stripe_customer_id

    customer = stripe.Customer.create(email=user.email, name=user.username)
    profile.stripe_customer_id = customer.id
    profile.save(update_fields=["stripe_customer_id"])
    return customer.id


def create_checkout_session(user, price_id: str, success_url: str, cancel_url: str):
    customer_id = get_or_create_customer(user)
    return stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )


def create_billing_portal_session(user, return_url: str):
    customer_id = get_or_create_customer(user)
    return stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
