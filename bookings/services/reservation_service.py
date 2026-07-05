from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from ..models import Equipment, EquipmentReservation, EquipmentRental

class ReservationService:
    """Service for managing equipment reservations"""

    @staticmethod
    @transaction.atomic
    def create_reservation(equipment_id, user, start_date, end_date, purpose="", notes=""):
        """
        Create a new reservation with conflict detection
        """
        equipment = Equipment.objects.select_for_update().get(id=equipment_id)
        now = timezone.now()
        
        # Validate dates
        if start_date >= end_date:
            raise ValidationError("End date must be after start date")
        
        # ✅ Fixed: Check if the reservation has already ended
        if end_date < now:
            raise ValidationError("Cannot make reservations that have already ended")
        
        # Check if equipment is available
        if equipment.status not in ['AVAILABLE', 'RENTED']:
            raise ValidationError(f"Equipment '{equipment.name}' is not available for reservation")
        
        # Check for conflicting reservations
        conflict = EquipmentReservation.objects.filter(
            equipment=equipment,
            start_date__lt=end_date,
            end_date__gt=start_date,
            status__in=['PENDING', 'CONFIRMED']
        ).exists()
        
        if conflict:
            raise ValidationError("This equipment is already reserved for the selected dates")
        
        # Check for active rentals in the date range
        rental_conflict = EquipmentRental.objects.filter(
            equipment=equipment,
            status='CHECKED_OUT',
            checkout_date__lt=end_date,
            expected_return_date__gt=start_date
        ).exists()
        
        if rental_conflict:
            raise ValidationError("This equipment is currently rented during the selected dates")
        
        # Create reservation
        reservation = EquipmentReservation.objects.create(
            equipment=equipment,
            user=user,
            start_date=start_date,
            end_date=end_date,
            purpose=purpose,
            notes=notes,
            status='PENDING'
        )
        
        return reservation

    @staticmethod
    @transaction.atomic
    def confirm_reservation(reservation_id, user):
        """Confirm a reservation (staff only)"""
        # Add staff check
        if not user.is_staff:
            raise ValidationError("Only staff members can confirm reservations")
        
        reservation = EquipmentReservation.objects.select_for_update().get(id=reservation_id)
        
        # Check if valid to confirm
        if reservation.status != 'PENDING':
            raise ValidationError(f"Cannot confirm reservation with status: {reservation.get_status_display()}")
        
        if reservation.is_expired():
            raise ValidationError("This reservation has expired")
        
        # Check for conflicts again
        conflict = EquipmentReservation.objects.filter(
            equipment=reservation.equipment,
            start_date__lt=reservation.end_date,
            end_date__gt=reservation.start_date,
            status__in=['PENDING', 'CONFIRMED']
        ).exclude(id=reservation_id).exists()
        
        if conflict:
            raise ValidationError("A conflicting reservation has been made since this was created")
        
        # Confirm the reservation
        reservation.confirm()
        return reservation

    @staticmethod
    @transaction.atomic
    def cancel_reservation(reservation_id, user):
        """Cancel a reservation"""
        reservation = EquipmentReservation.objects.select_for_update().get(id=reservation_id)
        
        if reservation.user != user and not user.is_staff:
            raise ValidationError("You don't have permission to cancel this reservation")
        
        if not reservation.can_cancel():
            raise ValidationError(f"Cannot cancel reservation with status: {reservation.get_status_display()}")
        
        reservation.cancel()
        return reservation

    @staticmethod
    def get_available_equipment(start_date, end_date):
        """Get equipment available for reservation in date range"""
        # Get all equipment
        all_equipment = Equipment.objects.filter(status__in=['AVAILABLE', 'RENTED'])
        
        # Get reserved equipment in date range
        reserved_ids = EquipmentReservation.objects.filter(
            start_date__lt=end_date,
            end_date__gt=start_date,
            status__in=['PENDING', 'CONFIRMED']
        ).values_list('equipment_id', flat=True)
        
        # Get rented equipment in date range
        rented_ids = EquipmentRental.objects.filter(
            status='CHECKED_OUT',
            checkout_date__lt=end_date,
            expected_return_date__gt=start_date
        ).values_list('equipment_id', flat=True)
        
        # Exclude reserved and rented equipment
        available = all_equipment.exclude(id__in=reserved_ids).exclude(id__in=rented_ids)
        
        return available

    @staticmethod
    def get_user_reservations(user, status=None):
        """Get reservations for a user"""
        queryset = EquipmentReservation.objects.filter(user=user)
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by('-created_at')

    @staticmethod
    def get_upcoming_reservations(user, days=7):
        """Get upcoming reservations for a user"""
        now = timezone.now()
        future = now + timedelta(days=days)
        return EquipmentReservation.objects.filter(
            user=user,
            start_date__gte=now,
            start_date__lte=future,
            status__in=['PENDING', 'CONFIRMED']
        ).order_by('start_date')

    @staticmethod
    def expire_pending_reservations():
        """Expire all pending reservations that have passed their expiration"""
        expired = EquipmentReservation.objects.filter(
            status='PENDING',
            expires_at__lte=timezone.now()
        )
        for reservation in expired:
            reservation.expire()
        return expired.count()

    # ✅ FIX: This method must be indented at the same level as other methods
    @staticmethod
    def auto_complete_reservations():
        """
        Auto-complete reservations that have passed their end date.
        Returns a dictionary with completion statistics.
        """
        now = timezone.now()
        
        # Find all active reservations that have ended
        completed = EquipmentReservation.objects.filter(
            status__in=['PENDING', 'CONFIRMED'],
            end_date__lte=now
        ).select_related('equipment')
        
        total_count = completed.count()
        successful_count = 0
        error_count = 0
        errors = []
        
        for reservation in completed:
            try:
                with transaction.atomic():
                    # Check if equipment still exists
                    if not reservation.equipment:
                        continue
                    
                    reservation.complete()
                    successful_count += 1
                    
            except Exception as e:
                error_count += 1
                errors.append(f"Reservation #{reservation.id}: {str(e)}")
        
        return {
            'total': total_count,
            'successful': successful_count,
            'error_count': error_count,
            'errors': errors
        }

    @staticmethod
    def get_calendar_data(year=None, month=None):
        """Get reservation data for calendar view"""
        import calendar
        from datetime import datetime
        
        if not year:
            year = timezone.now().year
        if not month:
            month = timezone.now().month
        
        # Get reservations for the month
        start_date = timezone.make_aware(datetime(year, month, 1))
        if month == 12:
            end_date = timezone.make_aware(datetime(year + 1, 1, 1))
        else:
            end_date = timezone.make_aware(datetime(year, month + 1, 1))
        
        reservations = EquipmentReservation.objects.filter(
            start_date__gte=start_date,
            start_date__lt=end_date,
            status__in=['PENDING', 'CONFIRMED']
        ).select_related('equipment', 'user')
        
        # Build calendar data
        cal = calendar.monthcalendar(year, month)
        calendar_data = []
        
        for week in cal:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append(None)
                else:
                    date = timezone.make_aware(datetime(year, month, day))
                    day_reservations = reservations.filter(
                        start_date__date=date.date()
                    )
                    week_data.append({
                        'day': day,
                        'date': date,
                        'reservations': day_reservations,
                        'count': day_reservations.count()
                    })
            calendar_data.append(week_data)
        
        return {
            'calendar_data': calendar_data,
            'month': month,
            'year': year,
            'month_name': calendar.month_name[month],
        }