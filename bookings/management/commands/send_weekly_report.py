from django.core.management.base import BaseCommand
from bookings.email_reports import EmailReportService

class Command(BaseCommand):
    help = 'Send weekly analytics report to admins'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Send report to specific email address'
        )

    def handle(self, *args, **options):
        self.stdout.write('Sending weekly analytics report...')
        
        recipient_list = None
        if options.get('email'):
            recipient_list = [options['email']]
        
        success = EmailReportService.send_weekly_report(recipient_list)
        
        if success:
            self.stdout.write(self.style.SUCCESS('Weekly report sent successfully!'))
        else:
            self.stdout.write(self.style.ERROR('Failed to send weekly report'))