# bookings/management/commands/complete_reservations.py

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from bookings.services.reservation_service import ReservationService
from bookings.models import EquipmentReservation
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Auto-complete reservations that have passed their end date'
    
    def add_arguments(self, parser):
        # Optional arguments for flexibility
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be completed without actually completing',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='Only complete reservations older than X days (optional)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each reservation',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of reservations to process',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting auto-completion process...'))
        self.stdout.write(f'⏰ Current time: {timezone.now()}')
        
        # Build the query
        query = EquipmentReservation.objects.filter(
            status__in=['PENDING', 'CONFIRMED'],
            end_date__lte=timezone.now()
        ).select_related('equipment')
        
        # Apply days filter if specified
        if options.get('days'):
            cutoff_date = timezone.now() - timezone.timedelta(days=options['days'])
            query = query.filter(end_date__lte=cutoff_date)
            self.stdout.write(f'📅 Only processing reservations older than {options["days"]} days')
        
        # Apply limit if specified
        if options.get('limit'):
            query = query[:options['limit']]
            self.stdout.write(f'🔢 Limiting to {options["limit"]} reservations')
        
        total_count = query.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING('⚠️ No reservations to complete'))
            return
        
        self.stdout.write(f'📊 Found {total_count} reservations to process')
        
        # Dry run mode
        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made'))
            
            # Show what would be completed
            for reservation in query[:10]:  # Show first 10
                self.stdout.write(
                    f'  • #{reservation.id} - {reservation.equipment.name} '
                    f'(Ended: {reservation.end_date.strftime("%Y-%m-%d %H:%M")})'
                )
            
            if total_count > 10:
                self.stdout.write(f'  ... and {total_count - 10} more')
            
            self.stdout.write(self.style.WARNING('✅ Dry run completed. No changes were made.'))
            return
        
        # Process the completions
        try:
            with transaction.atomic():
                completed_count = 0
                error_count = 0
                
                for reservation in query:
                    try:
                        # Use the service method or direct call
                        reservation.complete()
                        completed_count += 1
                        
                        if options.get('verbose'):
                            self.stdout.write(
                                f'  ✅ Completed #{reservation.id} - {reservation.equipment.name}'
                            )
                    
                    except Exception as e:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(f'  ❌ Error on #{reservation.id}: {str(e)}')
                        )
                        logger.error(f'Error completing reservation {reservation.id}: {e}')
                
                # Summary
                self.stdout.write('\n' + '='*50)
                self.stdout.write(self.style.SUCCESS('📊 COMPLETION SUMMARY'))
                self.stdout.write(f'  • Total processed: {total_count}')
                self.stdout.write(f'  • Successfully completed: {completed_count}')
                self.stdout.write(f'  • Errors: {error_count}')
                self.stdout.write('='*50)
                
                if completed_count > 0:
                    self.stdout.write(self.style.SUCCESS(f'✅ Successfully completed {completed_count} reservations!'))
                else:
                    self.stdout.write(self.style.WARNING('⚠️ No reservations were completed'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Fatal error: {str(e)}'))
            logger.error(f'Fatal error in complete_reservations command: {e}')
            raise CommandError(f'Failed to complete reservations: {str(e)}')