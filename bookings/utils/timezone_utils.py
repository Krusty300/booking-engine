from django.utils import timezone
from datetime import datetime, timedelta
import pytz

def get_current_time():
    """Get current time in the project's timezone"""
    return timezone.now()

def get_current_date():
    """Get current date in the project's timezone"""
    return timezone.now().date()

def format_datetime(dt, format_string='%b %d, %Y %I:%M %p'):
    """Format datetime for display"""
    if dt is None:
        return ''
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt.strftime(format_string)

def format_date(dt, format_string='%b %d, %Y'):
    """Format date for display"""
    if dt is None:
        return ''
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt.strftime(format_string)

def format_time(dt, format_string='%I:%M %p'):
    """Format time for display"""
    if dt is None:
        return ''
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt.strftime(format_string)

def is_past(dt):
    """Check if a datetime is in the past"""
    if dt is None:
        return True
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt < timezone.now()

def is_future(dt):
    """Check if a datetime is in the future"""
    if dt is None:
        return False
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt > timezone.now()

def is_today(dt):
    """Check if a datetime is today"""
    if dt is None:
        return False
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt.date() == timezone.now().date()

def make_aware_if_naive(dt):
    """Make a datetime aware if it's naive"""
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt

def get_local_timezone():
    """Get the local timezone from settings"""
    import pytz
    from django.conf import settings
    return pytz.timezone(settings.TIME_ZONE)

def convert_to_local(dt):
    """Convert a datetime to local timezone"""
    if dt is None:
        return None
    local_tz = get_local_timezone()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt.astimezone(local_tz)

def get_time_slots_for_date(date_obj, start_hour=9, end_hour=17, interval_hours=1):
    """Generate time slots for a given date"""
    slots = []
    current = datetime.combine(date_obj, datetime.min.time().replace(hour=start_hour))
    current = timezone.make_aware(current)
    end = datetime.combine(date_obj, datetime.min.time().replace(hour=end_hour))
    end = timezone.make_aware(end)
    
    while current < end:
        slot_end = current + timedelta(hours=interval_hours)
        slots.append({
            'start': current,
            'end': slot_end,
            'start_display': format_time(current),
            'end_display': format_time(slot_end),
            'is_past': is_past(current)
        })
        current = slot_end
    
    return slots

def validate_booking_time(start_time, end_time):
    """Validate booking times"""
    errors = []
    
    # Check if times are provided
    if not start_time or not end_time:
        errors.append("Start time and end time are required.")
        return errors
    
    # Make times aware if needed
    start_time = make_aware_if_naive(start_time)
    end_time = make_aware_if_naive(end_time)
    
    # Check if end time is after start time
    if end_time <= start_time:
        errors.append("End time must be after start time.")
    
    # Check if booking is in the past
    if is_past(start_time):
        errors.append("Cannot book in the past.")
    
    # Check if booking is too far in the future (max 1 year)
    max_future = timezone.now() + timedelta(days=365)
    if start_time > max_future:
        errors.append("Cannot book more than 1 year in advance.")
    
    return errors

def get_available_days(resource, start_date=None, days=30):
    """Get available days for a resource"""
    if start_date is None:
        start_date = get_current_date()
    
    available_days = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        if date < get_current_date():
            continue
        
        # Check if any slot is available for this date
        slots = get_time_slots_for_date(date)
        has_available = False
        total_slots = len(slots)
        available_slots = 0
        
        for slot in slots:
            if not slot['is_past']:
                # Check if slot is booked
                is_booked = Booking.objects.filter(
                    resource=resource,
                    start_time__lt=slot['end'],
                    end_time__gt=slot['start'],
                    status__in=['PENDING', 'CONFIRMED']
                ).exists()
                if not is_booked:
                    available_slots += 1
                    has_available = True
        
        available_days.append({
            'date': date,
            'total_slots': total_slots,
            'available_slots': available_slots,
            'has_available': has_available,
            'is_fully_booked': not has_available and total_slots > 0
        })
    
    return available_days