from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('data/', views.analytics_data, name='analytics_data'),
    path('export/', views.export_report, name='export_report'),
]