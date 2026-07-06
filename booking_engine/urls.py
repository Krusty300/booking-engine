from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from bookings import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('logout/', views.custom_logout, name='logout'),  # Custom logout (GET allowed)
    path('analytics/', views.admin_dashboard, name='admin_dashboard'),
    path('analytics/export/', views.export_report, name='export_report'),  # Keep this
    path('', include('bookings.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
