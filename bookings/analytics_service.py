from django.db import models
from django.db.models import Sum, Count, Avg, Q, F, ExpressionWrapper, DecimalField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from bookings.models import Booking, Resource, UserProfile, Review, AnalyticsEvent

class AnalyticsService:
    """Service for handling analytics and statistics"""
    
    @staticmethod
    def get_dashboard_stats(request=None):
        """Get all dashboard statistics"""
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        last_7_days = now - timedelta(days=7)
        
        # --- Bookings ---
        total_bookings = Booking.objects.count()
        recent_bookings = Booking.objects.filter(created_at__gte=last_30_days).count()
        recent_7_days = Booking.objects.filter(created_at__gte=last_7_days).count()
        
        # --- Users ---
        total_users = UserProfile.objects.count()
        new_users = UserProfile.objects.filter(created_at__gte=last_30_days).count()
        
        # ============================================================
        # ✅ REVENUE CALCULATION - Price per hour * Duration
        # ============================================================
        # Calculate total revenue for confirmed bookings
        total_revenue = Booking.objects.filter(
            status='CONFIRMED',
            resource__price_per_hour__isnull=False,
            resource__price_per_hour__gt=0
        ).annotate(
            duration_hours=ExpressionWrapper(
                (F('end_time') - F('start_time')) / timedelta(hours=1),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).aggregate(
            total=Coalesce(
                Sum(
                    F('resource__price_per_hour') * F('duration_hours')
                ),
                Value(Decimal('0.00'))
            )
        )['total'] or Decimal('0.00')
        
        # ============================================================
        # ✅ REVENUE GROWTH CALCULATION
        # ============================================================
        prev_30_days = now - timedelta(days=60)
        prev_30_revenue = Booking.objects.filter(
            status='CONFIRMED',
            resource__price_per_hour__isnull=False,
            resource__price_per_hour__gt=0,
            created_at__gte=prev_30_days,
            created_at__lt=last_30_days
        ).annotate(
            duration_hours=ExpressionWrapper(
                (F('end_time') - F('start_time')) / timedelta(hours=1),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).aggregate(
            total=Coalesce(
                Sum(
                    F('resource__price_per_hour') * F('duration_hours')
                ),
                Value(Decimal('0.00'))
            )
        )['total'] or Decimal('0.00')
        
        revenue_growth = AnalyticsService._calculate_growth(
            float(total_revenue), 
            float(prev_30_revenue)
        )
        
        # ============================================================
        # ✅ ADDITIONAL REVENUE STATS
        # ============================================================
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Revenue this month
        revenue_this_month = Booking.objects.filter(
            status='CONFIRMED',
            resource__price_per_hour__isnull=False,
            resource__price_per_hour__gt=0,
            created_at__gte=month_start
        ).annotate(
            duration_hours=ExpressionWrapper(
                (F('end_time') - F('start_time')) / timedelta(hours=1),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).aggregate(
            total=Coalesce(
                Sum(
                    F('resource__price_per_hour') * F('duration_hours')
                ),
                Value(Decimal('0.00'))
            )
        )['total'] or Decimal('0.00')
        
        # Revenue last month
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)
        revenue_last_month = Booking.objects.filter(
            status='CONFIRMED',
            resource__price_per_hour__isnull=False,
            resource__price_per_hour__gt=0,
            created_at__gte=last_month_start,
            created_at__lt=month_start
        ).annotate(
            duration_hours=ExpressionWrapper(
                (F('end_time') - F('start_time')) / timedelta(hours=1),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).aggregate(
            total=Coalesce(
                Sum(
                    F('resource__price_per_hour') * F('duration_hours')
                ),
                Value(Decimal('0.00'))
            )
        )['total'] or Decimal('0.00')
        
        # Revenue this week
        week_start = now - timedelta(days=now.weekday())
        revenue_this_week = Booking.objects.filter(
            status='CONFIRMED',
            resource__price_per_hour__isnull=False,
            resource__price_per_hour__gt=0,
            created_at__gte=week_start
        ).annotate(
            duration_hours=ExpressionWrapper(
                (F('end_time') - F('start_time')) / timedelta(hours=1),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).aggregate(
            total=Coalesce(
                Sum(
                    F('resource__price_per_hour') * F('duration_hours')
                ),
                Value(Decimal('0.00'))
            )
        )['total'] or Decimal('0.00')
        
        # ============================================================
        # ✅ MONTHLY REVENUE TREND (Last 6 months)
        # ============================================================
        monthly_revenue = []
        current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Generate data for the last 6 months (oldest to newest)
        for i in range(5, -1, -1):
            # Calculate month start and end
            month_end = current_month - timedelta(days=30 * i)
            month_start_date = month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_end_date = (month_start_date + timedelta(days=32)).replace(day=1)
            
            # Get revenue for this month
            month_revenue = Booking.objects.filter(
                status='CONFIRMED',
                resource__price_per_hour__isnull=False,
                resource__price_per_hour__gt=0,
                created_at__gte=month_start_date,
                created_at__lt=month_end_date
            ).annotate(
                duration_hours=ExpressionWrapper(
                    (F('end_time') - F('start_time')) / timedelta(hours=1),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            ).aggregate(
                total=Coalesce(
                    Sum(
                        F('resource__price_per_hour') * F('duration_hours')
                    ),
                    Value(Decimal('0.00'))
                )
            )['total'] or Decimal('0.00')
            
            monthly_revenue.append({
                'month': month_start_date.strftime('%B %Y'),
                'revenue': float(month_revenue)
            })
        
        # --- Average Rating ---
        avg_rating = Review.objects.filter(status='APPROVED').aggregate(
            avg=Avg('rating')
        )['avg'] or 0
        
        # --- Growth Calculations for Bookings ---
        prev_30_booking_count = Booking.objects.filter(
            created_at__gte=prev_30_days,
            created_at__lt=last_30_days
        ).count()
        booking_growth = AnalyticsService._calculate_growth(recent_bookings, prev_30_booking_count)
        
        # --- Growth Calculations for Users ---
        prev_30_user_count = UserProfile.objects.filter(
            created_at__gte=prev_30_days,
            created_at__lt=last_30_days
        ).count()
        user_growth = AnalyticsService._calculate_growth(new_users, prev_30_user_count)
        
        # --- Recent Activities ---
        recent_activities = AnalyticsService._get_recent_activities(limit=10)
        
        # --- Status Counts ---
        pending_count = Booking.objects.filter(status='PENDING').count()
        confirmed_count = Booking.objects.filter(status='CONFIRMED').count()
        completed_count = Booking.objects.filter(status='COMPLETED').count()
        cancelled_count = Booking.objects.filter(status='CANCELLED').count()
        
        # --- Average Booking Value ---
        total_bookings_count = Booking.objects.filter(status='CONFIRMED').count()
        avg_booking_value = float(total_revenue) / total_bookings_count if total_bookings_count > 0 else 0
        
        return {
            # Basic stats
            'total_bookings': total_bookings,
            'total_users': total_users,
            'total_revenue': float(total_revenue),
            'avg_rating': round(float(avg_rating), 1),
            
            # Growth percentages
            'booking_growth': booking_growth,
            'user_growth': user_growth,
            'revenue_growth': revenue_growth,
            
            # Additional revenue stats
            'revenue_this_month': float(revenue_this_month),
            'revenue_last_month': float(revenue_last_month),
            'revenue_this_week': float(revenue_this_week),
            'avg_booking_value': round(avg_booking_value, 2),
            'monthly_revenue': monthly_revenue,  # ✅ Added monthly revenue trend
            
            # Additional stats
            'recent_7_days': recent_7_days,
            'recent_30_days': recent_bookings,
            'new_users': new_users,
            'pending_count': pending_count,
            'confirmed_count': confirmed_count,
            'completed_count': completed_count,
            'cancelled_count': cancelled_count,
            
            # Recent activities
            'recent_activities': recent_activities,
        }
    
    @staticmethod
    def _calculate_growth(current, previous):
        """
        Calculate growth percentage between two numbers.
        Handles edge cases like division by zero.
        """
        # If both are 0, growth is 0%
        if current == 0 and previous == 0:
            return 0
        # If previous is 0 and current > 0, growth is 100%
        if previous == 0:
            return 100 if current > 0 else 0
        # Calculate percentage change
        growth = ((current - previous) / previous) * 100
        return round(growth, 1)
    
    @staticmethod
    def _get_recent_activities(limit=10):
        """Get recent activities from analytics events"""
        events = AnalyticsEvent.objects.all().order_by('-created_at')[:limit]
        activities = []
        
        if not events.exists():
            return [
                {
                    'icon': 'circle',
                    'text': 'No recent activity',
                    'time': timezone.now()
                }
            ]
        
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
        else:
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
        
        labels = []
        data = []
        
        for i in range(days):
            date = start_date + timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            labels.append(date.strftime('%b %d'))
            
            booking_count = next(
                (b['count'] for b in bookings if str(b['date']) == date_str),
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
        
        colors = {
            'PENDING': '#ffc107',
            'CONFIRMED': '#28a745',
            'COMPLETED': '#17a2b8',
            'CANCELLED': '#dc3545',
        }
        
        labels = []
        data = []
        color_list = []
        
        for status in statuses:
            status_key = status['status']
            labels.append(status_labels.get(status_key, status_key))
            data.append(status['count'])
            color_list.append(colors.get(status_key, '#6c757d'))
        
        return {
            'labels': labels,
            'data': data,
            'colors': color_list
        }
    
    @staticmethod
    def get_hourly_patterns():
        """Get hourly booking patterns"""
        bookings = Booking.objects.extra(
            select={'hour': "strftime('%H', start_time)"}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        hours = [str(i).zfill(2) + ':00' for i in range(24)]
        counts = [0] * 24
        
        for booking in bookings:
            try:
                hour = int(booking['hour'])
                if 0 <= hour < 24:
                    counts[hour] = booking['count']
            except (ValueError, TypeError):
                pass
        
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
        
        users_with_bookings = UserProfile.objects.filter(
            user__booking__isnull=False
        ).distinct().count()
        
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
                (u['count'] for u in new_users_trend if str(u['date']) == date_str),
                0
            )
            trend_data.append({
                'date': date.strftime('%b %d'),
                'count': count
            })
        
        engagement_rate = round((users_with_bookings / total_users * 100) if total_users > 0 else 0, 1)
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': total_users - active_users,
            'users_with_bookings': users_with_bookings,
            'new_users_trend': trend_data,
            'engagement_rate': engagement_rate
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
    
    @staticmethod
    def export_bookings_csv():
        """Export bookings data as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="bookings_export_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Resource', 'Customer', 'Start Time', 'End Time',
            'Status', 'Duration (hours)', 'Revenue', 'Notes', 'Created At'
        ])
        
        bookings = Booking.objects.select_related('resource', 'customer').all()
        for booking in bookings:
            duration = booking.get_duration()
            revenue = 0
            if booking.resource.price_per_hour and booking.status == 'CONFIRMED':
                revenue = booking.resource.price_per_hour * duration
            
            writer.writerow([
                booking.id,
                booking.resource.name,
                booking.customer.username,
                booking.start_time.strftime('%Y-%m-%d %H:%M'),
                booking.end_time.strftime('%Y-%m-%d %H:%M'),
                booking.get_status_display(),
                duration,
                f"${revenue:.2f}",
                booking.notes or '',
                booking.created_at.strftime('%Y-%m-%d %H:%M'),
            ])
        
        return response
    
    @staticmethod
    def export_users_csv():
        """Export users data as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="users_export_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Username', 'Email', 'First Name', 'Last Name',
            'Phone', 'Location', 'Total Bookings', 'Joined Date'
        ])
        
        users = UserProfile.objects.select_related('user').all()
        for profile in users:
            writer.writerow([
                profile.user.username,
                profile.user.email,
                profile.user.first_name,
                profile.user.last_name,
                profile.phone_number or '',
                profile.location or '',
                Booking.objects.filter(customer=profile.user).count(),
                profile.created_at.strftime('%Y-%m-%d'),
            ])
        
        return response
    
    @staticmethod
    def export_resources_csv():
        """Export resources data as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="resources_export_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Name', 'Category', 'Owner', 'Status',
            'Location', 'Price per Hour', 'Max Capacity',
            'Total Bookings', 'Total Revenue', 'Created At'
        ])
        
        resources = Resource.objects.select_related('category', 'owner').annotate(
            booking_count=Count('bookings')
        ).all()
        
        for resource in resources:
            total_revenue = 0
            for booking in resource.bookings.filter(status='CONFIRMED'):
                if resource.price_per_hour:
                    duration = booking.get_duration()
                    total_revenue += resource.price_per_hour * duration
            
            writer.writerow([
                resource.id,
                resource.name,
                resource.category.name if resource.category else 'Uncategorized',
                resource.owner.username if resource.owner else 'No owner',
                resource.get_status_display(),
                resource.location or '',
                resource.price_per_hour or 0,
                resource.max_capacity,
                resource.booking_count,
                f"${total_revenue:.2f}",
                resource.created_at.strftime('%Y-%m-%d %H:%M'),
            ])
        
        return response