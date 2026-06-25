from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from ..models import Booking, Resource, UserProfile

class AnalyticsService:
    """Service for analytics and reporting"""

    @staticmethod
    def get_dashboard_stats(request):
        """Get statistics for admin dashboard"""
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        # Booking stats
        total_bookings = Booking.objects.count()
        confirmed_bookings = Booking.objects.filter(status='CONFIRMED').count()
        cancelled_bookings = Booking.objects.filter(status='CANCELLED').count()
        completed_bookings = Booking.objects.filter(status='COMPLETED').count()
        
        # User stats
        total_users = UserProfile.objects.count()
        active_users = UserProfile.objects.filter(last_activity__gte=thirty_days_ago).count()
        
        # New users in last 30 days
        new_users = UserProfile.objects.filter(user__date_joined__gte=thirty_days_ago).count()
        
        # Revenue (if applicable)
        total_revenue = 0  # Calculate if you have a price field
        
        # Booking trends for last 30 days
        booking_trends = []
        for i in range(30):
            day = thirty_days_ago + timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
            count = Booking.objects.filter(created_at__gte=day_start, created_at__lte=day_end).count()
            booking_trends.append({
                'date': day.strftime('%Y-%m-%d'),
                'count': count
            })
        
        # Category distribution
        category_distribution = []
        for resource in Resource.objects.all():
            count = Booking.objects.filter(resource=resource).count()
            if count > 0:
                category_distribution.append({
                    'name': resource.name,
                    'count': count
                })
        
        # Status distribution
        status_distribution = [
            {'status': 'Confirmed', 'count': confirmed_bookings},
            {'status': 'Pending', 'count': Booking.objects.filter(status='PENDING').count()},
            {'status': 'Cancelled', 'count': cancelled_bookings},
            {'status': 'Completed', 'count': completed_bookings},
        ]
        
        # Popular resources
        popular_resources = Resource.objects.annotate(
            booking_count=Count('bookings')
        ).order_by('-booking_count')[:10]
        
        # Recent bookings
        recent_bookings = Booking.objects.all().order_by('-created_at')[:10]
        
        return {
            'total_bookings': total_bookings,
            'confirmed_bookings': confirmed_bookings,
            'cancelled_bookings': cancelled_bookings,
            'completed_bookings': completed_bookings,
            'total_users': total_users,
            'active_users': active_users,
            'new_users': new_users,
            'total_revenue': total_revenue,
            'booking_trends': booking_trends,
            'category_distribution': category_distribution,
            'status_distribution': status_distribution,
            'popular_resources': popular_resources,
            'recent_bookings': recent_bookings,
        }

    @staticmethod
    def get_booking_analytics(period='month'):
        """Get booking analytics for charts"""
        # Simplified version - expand as needed
        return {
            'period': period,
            'data': []
        }

    @staticmethod
    def get_user_analytics():
        """Get user analytics"""
        return {
            'total_users': UserProfile.objects.count(),
            'active_users': 0,
            'inactive_users': 0,
            'new_users_trend': [],
            'users_with_bookings': 0,
            'users_with_resources': 0,
            'engagement_rate': 0,
            'top_users': []
        }

    @staticmethod
    def get_resource_analytics():
        """Get resource analytics"""
        return {
            'resource_popularity': [],
            'category_counts': [],
            'status_counts': [],
            'popular_hours': {}
        }

    @staticmethod
    def get_hourly_patterns():
        """Get hourly booking patterns"""
        return {}

    @staticmethod
    def get_weekly_trends():
        """Get weekly booking trends"""
        return {}

    @staticmethod
    def get_status_distribution():
        """Get status distribution"""
        return {}

    @staticmethod
    def get_monthly_trends():
        """Get monthly booking trends"""
        return {}

    @staticmethod
    def export_bookings_csv():
        """Export bookings as CSV"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Resource', 'Customer', 'Start Time', 'End Time', 'Status', 'Created At'])
        
        for booking in Booking.objects.all():
            writer.writerow([
                booking.id,
                booking.resource.name,
                booking.customer.username,
                booking.start_time.strftime('%Y-%m-%d %H:%M'),
                booking.end_time.strftime('%Y-%m-%d %H:%M'),
                booking.get_status_display(),
                booking.created_at.strftime('%Y-%m-%d %H:%M')
            ])
        
        return output.getvalue()

    @staticmethod
    def export_users_csv():
        """Export users as CSV"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Username', 'Email', 'Date Joined', 'Last Login', 'Is Staff'])
        
        for profile in UserProfile.objects.all():
            user = profile.user
            writer.writerow([
                user.username,
                user.email,
                user.date_joined.strftime('%Y-%m-%d %H:%M'),
                user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else '',
                'Yes' if user.is_staff else 'No'
            ])
        
        return output.getvalue()

    @staticmethod
    def export_resources_csv():
        """Export resources as CSV"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Name', 'Description', 'Status', 'Owner', 'Created At'])
        
        for resource in Resource.objects.all():
            writer.writerow([
                resource.id,
                resource.name,
                resource.description,
                resource.get_status_display(),
                resource.owner.username if resource.owner else '',
                resource.created_at.strftime('%Y-%m-%d %H:%M')
            ])
        
        return output.getvalue()