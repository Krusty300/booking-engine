from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Booking, Resource

class BookingService:
    """Service class to handle booking creation with concurrency control"""

    @staticmethod
    @transaction.atomic
    def create_booking(resource_id, customer, start_time, end_time, notes=""):
        """
        Create a booking with database-level locking to prevent double-booking.
        Returns the created Booking object or raises an exception.
        """
        # Validate times
        if start_time >= end_time:
            raise ValidationError("End time must be after start time")

        if start_time < timezone.now():
            raise ValidationError("Cannot book in the past")

        # Lock the resource to check for conflicts
        # Using select_for_update() locks the row until transaction completes
        resource = Resource.objects.select_for_update().get(id=resource_id)

        # Check for overlapping bookings
        overlapping = Booking.objects.filter(
            resource=resource,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status__in=['PENDING', 'CONFIRMED']  # Don't count cancelled/completed
        ).exists()

        if overlapping:
            raise ValidationError("This time slot is already booked")

        # Create the booking
        booking = Booking.objects.create(
            resource=resource,
            customer=customer,
            start_time=start_time,
            end_time=end_time,
            status='CONFIRMED',  # Auto-confirm for simplicity
            notes=notes
        )

        return booking

    @staticmethod
    def get_available_slots(resource_id, date):
        """Get available time slots for a specific date"""
        from datetime import datetime
        resource = Resource.objects.get(id=resource_id)

        # Get all bookings for that day
        day_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        day_end = timezone.make_aware(datetime.combine(date, datetime.max.time()))

        booked_slots = Booking.objects.filter(
            resource=resource,
            start_time__gte=day_start,
            start_time__lte=day_end,
            status__in=['PENDING', 'CONFIRMED']
        ).values_list('start_time', 'end_time')

        return booked_slots

    @staticmethod
    def cancel_booking(booking_id, user):
        """Cancel a booking if it's not already cancelled or completed"""
        booking = Booking.objects.get(id=booking_id, customer=user)
        
        if booking.status in ['CANCELLED', 'COMPLETED']:
            raise ValidationError("This booking cannot be cancelled.")
        elif booking.start_time < timezone.now():
            raise ValidationError("Cannot cancel a booking that has already passed.")
        else:
            booking.status = 'CANCELLED'
            booking.save()
            return booking