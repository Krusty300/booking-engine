from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Booking, Resource, UserProfile, AnalyticsEvent, DailyAnalytics
from django.contrib.auth.models import User
import json
import calendar

class AnalyticsService:
    """Service for generating analytics data"""
    
    @staticmethod
    def get_dashboard_stats(request=None):
        """Get main dashboard statistics"""
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        
        # Booking statistics
        total_bookings = Booking.objects.count()
        confirmed_bookings = Booking.objects.filter(status='CONFIRMED').count()
        cancelled_bookings = Booking.objects.filter(status='CANCELLED').count()
        completed_bookings = Booking.objects.filter(status='COMPLETED').count()
        
        # Revenue calculation (if you have price fields)
        total_revenue = 0
        try:
            # If you have a price field on Booking
            # total_revenue = Booking.objects.filter(status='COMPLETED').aggregate(Sum('price'))['price__sum'] or 0
            pass
        except:
            total_revenue = 0
        
        # Recent bookings
        recent_bookings = Booking.objects.order_by('-created_at')[:10]
        
        # Popular resources
        popular_resources = Resource.objects.annotate(
            booking_count=Count('bookings')
        ).filter(booking_count__gt=0).order_by('-booking_count')[:10]
        
        # User statistics
        total_users = User.objects.count()
        active_users = User.objects.filter(
            last_login__gte=thirty_days_ago
        ).count()
        new_users = User.objects.filter(
            date_joined__gte=thirty_days_ago
        ).count()
        
        # Booking trends (last 30 days)
        booking_trends = []
        for i in range(30):
            date = now - timedelta(days=i)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            count = Booking.objects.filter(
                created_at__gte=day_start,
                created_at__lte=day_end
            ).count()
            booking_trends.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })
        booking_trends.reverse()
        
        # Category distribution
        category_distribution = []
        for category in Resource.objects.values('category__name').annotate(
            count=Count('id')
        ).order_by('-count'):
            if category['category__name']:
                category_distribution.append({
                    'name': category['category__name'],
                    'count': category['count']
                })
        
        # Status distribution
        status_distribution = []
        for status, label in Booking.STATUS_CHOICES:
            count = Booking.objects.filter(status=status).count()
            status_distribution.append({
                'status': label,
                'count': count
            })
        
        return {
            'total_bookings': total_bookings,
            'confirmed_bookings': confirmed_bookings,
            'cancelled_bookings': cancelled_bookings,
            'completed_bookings': completed_bookings,
            'total_revenue': total_revenue,
            'recent_bookings': recent_bookings,
            'popular_resources': popular_resources,
            'total_users': total_users,
            'active_users': active_users,
            'new_users': new_users,
            'booking_trends': booking_trends,
            'category_distribution': category_distribution,
            'status_distribution': status_distribution,
        }
    
    @staticmethod
    def get_booking_analytics(period='month'):
        """Get detailed booking analytics"""
        now = timezone.now()
        
        if period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        elif period == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=30)
        
        # Daily bookings
        daily_data = []
        for i in range(30):
            date = start_date + timedelta(days=i)
            if date > now:
                break
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            count = Booking.objects.filter(
                created_at__gte=day_start,
                created_at__lte=day_end
            ).count()
            daily_data.append({
                'date': date.strftime('%b %d'),
                'bookings': count
            })
        
        # Hourly distribution
        hourly_data = []
        for hour in range(24):
            count = Booking.objects.filter(
                created_at__hour=hour
            ).count()
            hourly_data.append({
                'hour': f'{hour:02d}:00',
                'count': count
            })
        
        # Weekly patterns (day of week)
        weekly_data = []
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for i, day in enumerate(days):
            count = Booking.objects.filter(
                created_at__week_day=i+1 if i < 6 else 7
            ).count()
            weekly_data.append({
                'day': day,
                'count': count
            })
        
        return {
            'daily_data': daily_data,
            'hourly_data': hourly_data,
            'weekly_data': weekly_data,
            'total_period_bookings': sum(d['bookings'] for d in daily_data),
        }
    
    @staticmethod
    def get_user_analytics():
        """Get user behavior analytics"""
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        
        # User activity
        active_users = User.objects.filter(
            last_login__gte=thirty_days_ago
        ).count()
        inactive_users = User.objects.filter(
            last_login__lt=thirty_days_ago
        ).count()
        
        # New users trend
        new_users_trend = []
        for i in range(30):
            date = now - timedelta(days=i)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            count = User.objects.filter(
                date_joined__gte=day_start,
                date_joined__lte=day_end
            ).count()
            new_users_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })
        new_users_trend.reverse()
        
        # Top users by bookings
        top_users = User.objects.annotate(
            booking_count=Count('booking')
        ).filter(booking_count__gt=0).order_by('-booking_count')[:10]
        
        # User engagement metrics
        total_users = User.objects.count()
        users_with_bookings = User.objects.filter(booking__isnull=False).distinct().count()
        # FIXED: Use 'resources' (plural) instead of 'resource'
        users_with_resources = User.objects.filter(resources__isnull=False).distinct().count()
        
        return {
            'active_users': active_users,
            'inactive_users': inactive_users,
            'new_users_trend': new_users_trend,
            'top_users': top_users,
            'total_users': total_users,
            'users_with_bookings': users_with_bookings,
            'users_with_resources': users_with_resources,
            'engagement_rate': (users_with_bookings / total_users * 100) if total_users > 0 else 0,
        }
    
    @staticmethod
    def get_resource_analytics():
        """Get resource analytics"""
        # Resource popularity
        resource_popularity = Resource.objects.annotate(
            booking_count=Count('bookings')
        ).order_by('-booking_count')[:10]
        
        # Resource by category
        category_counts = Resource.objects.values('category__name').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Resource status distribution
        status_counts = Resource.objects.values('status').annotate(
            count=Count('id')
        )
        
        # Most booked resources (by hour)
        popular_hours = {}
        for resource in Resource.objects.annotate(booking_count=Count('bookings')).filter(booking_count__gt=0)[:5]:
            hours = Booking.objects.filter(resource=resource).values('start_time__hour').annotate(
                count=Count('id')
            ).order_by('-count')[:3]
            popular_hours[resource.name] = [
                {'hour': h['start_time__hour'], 'count': h['count']} for h in hours
            ]
        
        return {
            'resource_popularity': resource_popularity,
            'category_counts': category_counts,
            'status_counts': status_counts,
            'popular_hours': popular_hours,
        }
    
    @staticmethod
    def export_bookings_csv():
        """Export bookings data to CSV format"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Booking ID', 'Resource', 'Customer', 'Start Time', 'End Time',
            'Status', 'Created At', 'Notes'
        ])
        
        # Write data
        for booking in Booking.objects.select_related('resource', 'customer').order_by('-created_at'):
            writer.writerow([
                booking.id,
                booking.resource.name,
                booking.customer.username,
                booking.start_time.strftime('%Y-%m-%d %H:%M'),
                booking.end_time.strftime('%Y-%m-%d %H:%M'),
                booking.get_status_display(),
                booking.created_at.strftime('%Y-%m-%d %H:%M'),
                booking.notes or '',
            ])
        
        return output.getvalue()
    
    @staticmethod
    def export_users_csv():
        """Export users data to CSV format"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Username', 'Email', 'First Name', 'Last Name', 'Date Joined',
            'Last Login', 'Is Active', 'Is Staff', 'Total Bookings'
        ])
        
        # Write data
        for user in User.objects.all():
            booking_count = Booking.objects.filter(customer=user).count()
            writer.writerow([
                user.username,
                user.email,
                user.first_name,
                user.last_name,
                user.date_joined.strftime('%Y-%m-%d %H:%M'),
                user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else '',
                'Yes' if user.is_active else 'No',
                'Yes' if user.is_staff else 'No',
                booking_count,
            ])
        
        return output.getvalue()
    
    @staticmethod
    def export_resources_csv():
        """Export resources data to CSV format"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Resource ID', 'Name', 'Description', 'Owner', 'Status',
            'Category', 'Location', 'Price/Hour', 'Total Bookings'
        ])
        
        # Write data
        for resource in Resource.objects.select_related('owner', 'category').all():
            booking_count = Booking.objects.filter(resource=resource).count()
            writer.writerow([
                resource.id,
                resource.name,
                resource.description[:100] + '...' if len(resource.description) > 100 else resource.description,
                resource.owner.username if resource.owner else 'Unknown',
                resource.get_status_display(),
                resource.category.name if resource.category else 'Uncategorized',
                resource.location or '',
                str(resource.price_per_hour) if resource.price_per_hour else '0.00',
                booking_count,
            ])
        
        return output.getvalue()
    
    @staticmethod
    def track_event(user, event_type, request=None, metadata=None):
        """Track a user event for analytics"""
        try:
            event = AnalyticsEvent(
                user=user if user and user.is_authenticated else None,
                event_type=event_type,
                metadata=metadata or {},
            )
            
            if request:
                event.url = request.path
                event.ip_address = request.META.get('REMOTE_ADDR')
                event.user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            event.save()
            return event
        except Exception as e:
            print(f"Error tracking event: {e}")
            return None


    @staticmethod
    def get_hourly_patterns():
        """Get hourly booking patterns"""
        hourly_data = []
        for hour in range(24):
            count = Booking.objects.filter(
                start_time__hour=hour,
                status__in=['CONFIRMED', 'COMPLETED']
            ).count()
            hourly_data.append({
                'hour': f'{hour:02d}:00',
                'count': count
            })
        return hourly_data

    @staticmethod
    def get_weekly_trends():
        """Get weekly booking trends (last 7 days)"""
        weekly_data = []
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        
        for i, day in enumerate(days):
            # Get bookings for each day of the week
            count = Booking.objects.filter(
                start_time__week_day=i+1 if i < 6 else 7,
                status__in=['CONFIRMED', 'COMPLETED']
            ).count()
            weekly_data.append({
                'day': day,
                'count': count
            })
        return weekly_data

    @staticmethod
    def get_status_distribution():
        """Get booking status distribution"""
        status_data = []
        status_colors = {
            'CONFIRMED': '#28a745',
            'PENDING': '#ffc107',
            'CANCELLED': '#dc3545',
            'COMPLETED': '#17a2b8'
        }
        for status, label in Booking.STATUS_CHOICES:
            count = Booking.objects.filter(status=status).count()
            status_data.append({
                'status': label,
                'count': count,
                'color': status_colors.get(status, '#6c757d')
            })
        return status_data

    @staticmethod
    def get_monthly_trends():
        """Get monthly booking trends (last 6 months)"""
        now = timezone.now()
        monthly_data = []
        
        for i in range(6):
            month = now.replace(day=1) - timedelta(days=30*i)
            month_start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Get next month
            if month.month == 12:
                month_end = month.replace(year=month.year+1, month=1, day=1) - timedelta(seconds=1)
            else:
                month_end = month.replace(month=month.month+1, day=1) - timedelta(seconds=1)
            
            count = Booking.objects.filter(
                created_at__gte=month_start,
                created_at__lte=month_end,
                status__in=['CONFIRMED', 'COMPLETED']
            ).count()
            
            monthly_data.append({
                'month': month.strftime('%b %Y'),
                'count': count
            })
        
        monthly_data.reverse()
        return monthly_data
