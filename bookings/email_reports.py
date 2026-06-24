from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from .analytics_service import AnalyticsService
import csv
from io import StringIO

class EmailReportService:
    """Service for sending email reports"""
    
    @staticmethod
    def send_weekly_report(recipient_list=None):
        """Send weekly analytics report via email"""
        if not recipient_list:
            # Send to all admin users
            recipient_list = User.objects.filter(is_staff=True).values_list('email', flat=True)
            recipient_list = [email for email in recipient_list if email]
        
        if not recipient_list:
            return False
        
        # Get data for report
        stats = AnalyticsService.get_dashboard_stats()
        weekly_data = AnalyticsService.get_weekly_trends()
        status_data = AnalyticsService.get_status_distribution()
        top_resources = stats.get('popular_resources', [])
        
        context = {
            'stats': stats,
            'weekly_data': weekly_data,
            'status_data': status_data,
            'top_resources': top_resources,
            'report_date': timezone.now(),
        }
        
        # Render email templates
        html_message = render_to_string('emails/weekly_report.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        try:
            send_mail(
                subject=f'Weekly Analytics Report - {timezone.now().strftime("%B %d, %Y")}',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Error sending weekly report: {e}")
            return False
    
    @staticmethod
    def generate_csv_report():
        """Generate CSV report for email attachment"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Weekly Analytics Report'])
        writer.writerow([f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M")}'])
        writer.writerow([])
        
        # Summary
        stats = AnalyticsService.get_dashboard_stats()
        writer.writerow(['Summary Statistics'])
        writer.writerow(['Total Bookings', stats.get('total_bookings', 0)])
        writer.writerow(['Confirmed', stats.get('confirmed_bookings', 0)])
        writer.writerow(['Cancelled', stats.get('cancelled_bookings', 0)])
        writer.writerow(['Completed', stats.get('completed_bookings', 0)])
        writer.writerow(['Total Users', stats.get('total_users', 0)])
        writer.writerow(['Active Users (30d)', stats.get('active_users', 0)])
        writer.writerow([])
        
        # Top Resources
        writer.writerow(['Popular Resources'])
        writer.writerow(['Resource', 'Bookings'])
        for resource in stats.get('popular_resources', [])[:10]:
            writer.writerow([resource.name, resource.booking_count])
        
        return output.getvalue()