from django import template
from django.contrib.auth.models import AnonymousUser

register = template.Library()

@register.filter
def can_manage(equipment, user):
    """Check if user can manage equipment"""
    if not user or isinstance(user, AnonymousUser):
        return False
    return user.is_staff or equipment.owner == user