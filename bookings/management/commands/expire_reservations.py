from django.core.management.base import BaseCommand
from django.utils import timezone
from bookings.services.reservation_service import ReservationService

class Command(BaseCommand):
    help = 'Expire pending reservations and auto-complete completed ones'

    def handle(self, *args, **options):
        self.stdout.write('Processing reservations...')
        
        # Expire pending reservations
        expired = ReservationService.expire_pending_reservations()
        self.stdout.write(f' Expired {expired} pending reservations')
        
        # Auto-complete reservations
        completed = ReservationService.auto_complete_reservations()
        self.stdout.write(f' Completed {completed} reservations')
        
        self.stdout.write(' Reservation processing complete!')