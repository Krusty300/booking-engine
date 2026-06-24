from .analytics_service import AnalyticsService

class AnalyticsMiddleware:
    """Middleware to track page views"""
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Track page views (skip admin and static)
        if not request.path.startswith('/admin/') and not request.path.startswith('/static/'):
            try:
                AnalyticsService.track_event(
                    user=request.user if request.user.is_authenticated else None,
                    event_type='VIEW',
                    request=request,
                    metadata={'method': request.method}
                )
            except Exception as e:
                # Silently fail if analytics tracking fails
                pass
        
        return response