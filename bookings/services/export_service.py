from django.http import HttpResponse
from ..models import Booking, Resource, UserProfile
import csv
from io import BytesIO

class ExportService:
    """Service for exporting data in various formats"""

    @staticmethod
    def export_to_excel(report_type):
        """Export data to Excel format"""
        # For now, return CSV as bytes (you can add xlsx support later)
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        if report_type == 'bookings':
            writer.writerow(['ID', 'Resource', 'Customer', 'Start Time', 'End Time', 'Status'])
            for booking in Booking.objects.all():
                writer.writerow([
                    booking.id,
                    booking.resource.name,
                    booking.customer.username,
                    booking.start_time.strftime('%Y-%m-%d %H:%M'),
                    booking.end_time.strftime('%Y-%m-%d %H:%M'),
                    booking.get_status_display()
                ])
        elif report_type == 'users':
            writer.writerow(['Username', 'Email', 'Date Joined', 'Is Staff'])
            for profile in UserProfile.objects.all():
                user = profile.user
                writer.writerow([
                    user.username,
                    user.email,
                    user.date_joined.strftime('%Y-%m-%d %H:%M'),
                    'Yes' if user.is_staff else 'No'
                ])
        elif report_type == 'resources':
            writer.writerow(['ID', 'Name', 'Description', 'Status', 'Owner'])
            for resource in Resource.objects.all():
                writer.writerow([
                    resource.id,
                    resource.name,
                    resource.description,
                    resource.get_status_display(),
                    resource.owner.username if resource.owner else ''
                ])
        
        # Return as BytesIO for Excel-like response
        return BytesIO(output.getvalue().encode('utf-8'))

    @staticmethod
    def export_to_pdf(report_type):
        """Export data to PDF format"""
        # For now, return CSV as bytes (you can add PDF support later)
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        if report_type == 'bookings':
            writer.writerow(['ID', 'Resource', 'Customer', 'Start Time', 'End Time', 'Status'])
            for booking in Booking.objects.all():
                writer.writerow([
                    booking.id,
                    booking.resource.name,
                    booking.customer.username,
                    booking.start_time.strftime('%Y-%m-%d %H:%M'),
                    booking.end_time.strftime('%Y-%m-%d %H:%M'),
                    booking.get_status_display()
                ])
        
        # Return as BytesIO
        return BytesIO(output.getvalue().encode('utf-8'))