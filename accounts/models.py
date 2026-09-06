from django.conf import settings
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    PLAN_CHOICES = [
        ("free", "Free"),
        ("pro", "Pro"),
        ("unlimited", "Unlimited"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    stripe_customer_id = models.CharField(max_length=255, blank=True, default="")
    stripe_subscription_id = models.CharField(max_length=255, blank=True, default="")
    subscription_active = models.BooleanField(default=False)

    # Usage counters reset monthly by a scheduled task (see ingestion/tasks.py: reset_usage_counters)
    books_processed_this_period = models.PositiveIntegerField(default=0)
    questions_asked_this_period = models.PositiveIntegerField(default=0)
    period_started_at = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.plan})"

    def limits(self):
        from django.conf import settings as dj_settings
        return dj_settings.PLAN_LIMITS.get(self.plan, dj_settings.PLAN_LIMITS["free"])

    def can_process_book(self):
        return self.books_processed_this_period < self.limits()["books_per_month"]

    def can_ask_question(self):
        return self.questions_asked_this_period < self.limits()["questions_per_month"]
