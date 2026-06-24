from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Booking, Resource
from .utils.timezone_utils import validate_booking_time, make_aware_if_naive, is_past

class BookingService:
    """Service class to handle booking creation with concurrency control"""
    
    @staticmethod
    @transaction.atomic
    def create_booking(resource_id, customer, start_time, end_time, notes=None):
        """
        Create a booking with database-level locking to prevent double-booking.
        Returns the created Booking object or raises an exception.
        """
        # Make times aware if needed
        start_time = make_aware_if_naive(start_time)
        end_time = make_aware_if_naive(end_time)
        
        # Validate times
        errors = validate_booking_time(start_time, end_time)
        if errors:
            raise ValidationError(" ".join(errors))
        
        # Lock the resource to check for conflicts
        resource = Resource.objects.select_for_update().get(id=resource_id)
        
        # Check for overlapping bookings
        overlapping = Booking.objects.filter(
            resource=resource,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status__in=['PENDING', 'CONFIRMED']
        ).exists()
        
        if overlapping:
            raise ValidationError("This time slot is already booked")
        
        # Create the booking
        booking = Booking.objects.create(
            resource=resource,
            customer=customer,
            start_time=start_time,
            end_time=end_time,
            status='CONFIRMED',
            notes=notes
        )
        
        return booking