from django.contrib import admin
from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "subscription_active", "books_processed_this_period", "questions_asked_this_period")
    list_filter = ("plan", "subscription_active")
    search_fields = ("user__username", "user__email", "stripe_customer_id")
