from django.db import models
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from datetime import datetime, timedelta
from bookings.models import Booking, Resource, UserProfile, Review, AnalyticsEvent

class AnalyticsService:
    """Service for handling analytics and statistics"""
    
    @staticmethod
    def get_dashboard_stats(request=None):
        """Get all dashboard statistics"""
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        last_7_days = now - timedelta(days=7)
        
        # Total bookings
        total_bookings = Booking.objects.count()
        
        # Bookings in last 30 days
        recent_bookings = Booking.objects.filter(created_at__gte=last_30_days).count()
        
        # Total users
        total_users = UserProfile.objects.count()
        
        # New users in last 30 days
        new_users = UserProfile.objects.filter(created_at__gte=last_30_days).count()
        
        # Total revenue (assuming price_per_hour * duration)
        total_revenue = Booking.objects.filter(
            status='CONFIRMED',
            resource__price_per_hour__isnull=False
        ).aggregate(
            total=Sum(
                models.ExpressionWrapper(
                    models.F('resource__price_per_hour') * 
                    models.F('end_time') - models.F('start_time'),
                    output_field=models.DecimalField()
                )
            )
        )['total'] or 0
        
        # Average rating
        avg_rating = Review.objects.filter(status='APPROVED').aggregate(
            avg=models.Avg('rating')
        )['avg'] or 0
        
        # Calculate growth percentages
        prev_30_days = now - timedelta(days=60)
        prev_30_booking_count = Booking.objects.filter(
            created_at__gte=prev_30_days,
            created_at__lt=last_30_days
        ).count()
        
        booking_growth = AnalyticsService._calculate_growth(recent_bookings, prev_30_booking_count)
        
        prev_30_user_count = UserProfile.objects.filter(
            created_at__gte=prev_30_days,
            created_at__lt=last_30_days
        ).count()
        
        user_growth = AnalyticsService._calculate_growth(new_users, prev_30_user_count)
        
        # Recent activities
        recent_activities = AnalyticsService._get_recent_activities(limit=10)
        
        return {
            'total_bookings': total_bookings,
            'total_users': total_users,
            'total_revenue': float(total_revenue),
            'avg_rating': round(float(avg_rating), 1),
            'booking_growth': booking_growth,
            'user_growth': user_growth,
            'revenue_growth': 12,  # Placeholder
            'recent_activities': recent_activities,
        }
    
    @staticmethod
    def _calculate_growth(current, previous):
        """Calculate growth percentage between two numbers"""
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100)
    
    @staticmethod
    def _get_recent_activities(limit=10):
        """Get recent activities from analytics events"""
        events = AnalyticsEvent.objects.all().order_by('-created_at')[:limit]
        activities = []
        
        for event in events:
            activity = {
                'icon': 'circle',
                'text': f"{event.get_event_type_display()}",
                'time': event.created_at
            }
            
            if event.user:
                activity['text'] = f"{event.user.username} {activity['text'].lower()}"
            
            if event.metadata and 'resource_name' in event.metadata:
                activity['text'] += f" - {event.metadata['resource_name']}"
            
            activities.append(activity)
        
        return activities
    
    @staticmethod
    def get_booking_analytics(period='month'):
        """Get booking analytics for charts"""
        now = timezone.now()
        
        if period == '7d':
            start_date = now - timedelta(days=7)
            days = 7
        elif period == '90d':
            start_date = now - timedelta(days=90)
            days = 90
        else:  # 30d default
            start_date = now - timedelta(days=30)
            days = 30
        
        # Get bookings grouped by date
        bookings = Booking.objects.filter(
            created_at__gte=start_date
        ).extra(
            select={'date': 'date(created_at)'}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # Create labels and data
        labels = []
        data = []
        
        for i in range(days):
            date = start_date + timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            labels.append(date.strftime('%b %d'))
            
            booking_count = next(
                (b['count'] for b in bookings if b['date'].strftime('%Y-%m-%d') == date_str),
                0
            )
            data.append(booking_count)
        
        return {
            'labels': labels,
            'data': data
        }
    
    @staticmethod
    def get_status_distribution():
        """Get booking status distribution"""
        statuses = Booking.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        status_labels = {
            'PENDING': 'Pending',
            'CONFIRMED': 'Confirmed',
            'COMPLETED': 'Completed',
            'CANCELLED': 'Cancelled',
        }
        
        labels = []
        data = []
        
        for status in statuses:
            labels.append(status_labels.get(status['status'], status['status']))
            data.append(status['count'])
        
        return {
            'labels': labels,
            'data': data
        }
    
    @staticmethod
    def get_hourly_patterns():
        """Get hourly booking patterns"""
        # Get bookings grouped by hour
        bookings = Booking.objects.extra(
            select={'hour': "strftime('%H', start_time)"}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        # Create full 24-hour data
        hours = [str(i).zfill(2) + ':00' for i in range(24)]
        counts = [0] * 24
        
        for booking in bookings:
            hour = int(booking['hour'])
            if 0 <= hour < 24:
                counts[hour] = booking['count']
        
        return {
            'labels': hours,
            'data': counts
        }
    
    @staticmethod
    def get_resource_analytics():
        """Get resource analytics"""
        # Get popular resources
        popular_resources = Resource.objects.annotate(
            booking_count=Count('bookings')
        ).filter(
            booking_count__gt=0
        ).order_by('-booking_count')[:10]
        
        popularity = []
        for resource in popular_resources:
            popularity.append({
                'name': resource.name,
                'count': resource.booking_count
            })
        
        # Category distribution
        category_distribution = Resource.objects.values('category__name').annotate(
            count=Count('id')
        ).order_by('-count')
        
        categories = []
        for cat in category_distribution:
            categories.append({
                'name': cat['category__name'] or 'Uncategorized',
                'count': cat['count']
            })
        
        return {
            'popularity': popularity,
            'categories': categories
        }
    
    @staticmethod
    def get_user_analytics():
        """Get user analytics"""
        total_users = UserProfile.objects.count()
        active_users = UserProfile.objects.filter(
            last_activity__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # Users with bookings
        users_with_bookings = UserProfile.objects.filter(
            user__booking__isnull=False
        ).distinct().count()
        
        # New users trend (last 30 days)
        now = timezone.now()
        start_date = now - timedelta(days=30)
        
        new_users_trend = UserProfile.objects.filter(
            created_at__gte=start_date
        ).extra(
            select={'date': 'date(created_at)'}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        trend_data = []
        for i in range(30):
            date = start_date + timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            count = next(
                (u['count'] for u in new_users_trend if u['date'].strftime('%Y-%m-%d') == date_str),
                0
            )
            trend_data.append({
                'date': date.strftime('%b %d'),
                'count': count
            })
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': total_users - active_users,
            'users_with_bookings': users_with_bookings,
            'new_users_trend': trend_data,
            'engagement_rate': round((users_with_bookings / total_users * 100) if total_users > 0 else 0, 1)
        }
    
    @staticmethod
    def get_weekly_trends():
        """Get weekly booking trends"""
        now = timezone.now()
        weeks = 8
        start_date = now - timedelta(weeks=weeks)
        
        trends = []
        for i in range(weeks):
            week_start = start_date + timedelta(weeks=i)
            week_end = week_start + timedelta(days=7)
            
            count = Booking.objects.filter(
                created_at__gte=week_start,
                created_at__lt=week_end
            ).count()
            
            trends.append({
                'week': f"Week {i+1}",
                'count': count,
                'start_date': week_start,
                'end_date': week_end
            })
        
        return {
            'labels': [t['week'] for t in trends],
            'data': [t['count'] for t in trends]
        }
    
    @staticmethod
    def get_monthly_trends():
        """Get monthly booking trends"""
        now = timezone.now()
        months = 12
        start_date = now - timedelta(days=365)
        
        trends = []
        for i in range(months):
            month_start = start_date + timedelta(days=30*i)
            month_end = month_start + timedelta(days=30)
            
            count = Booking.objects.filter(
                created_at__gte=month_start,
                created_at__lt=month_end
            ).count()
            
            trends.append({
                'month': month_start.strftime('%B %Y'),
                'count': count
            })
        
        return {
            'labels': [t['month'] for t in trends],
            'data': [t['count'] for t in trends]
        }
