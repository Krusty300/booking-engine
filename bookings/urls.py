from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'bookings'

urlpatterns = [
    # ============ EXPORT ============
    path('export/', views.export_data, name='export_data'),
    
    # ============ AUTHENTICATION ============
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('signup/', views.signup, name='signup'),

    # ============ RESOURCE LISTING AND BOOKING ============
    path('', views.resource_list, name='resource_list'),
    path('resources/<int:resource_id>/', views.resource_detail, name='resource_detail'),
    
    # ============ USER RESOURCE MANAGEMENT ============
    path('my-resources/', views.my_resources, name='my_resources'),
    path('resources/create/', views.create_resource, name='create_resource'),
    path('resources/<int:resource_id>/edit/', views.edit_resource, name='edit_resource'),
    path('resources/<int:resource_id>/delete/', views.delete_resource, name='delete_resource'),

    # ============ CATEGORY MANAGEMENT (Admin Only) ============
    path('categories/', views.manage_categories, name='manage_categories'),
    path('categories/create/', views.create_category, name='create_category'),
    path('categories/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('categories/<int:category_id>/delete/', views.delete_category, name='delete_category'),

    # ============ ADMIN RESOURCE MANAGEMENT ============
    path('resources-admin/', views.admin_manage_resources, name='admin_manage_resources'),
    path('resources-admin/<int:resource_id>/status/', views.admin_update_resource_status, name='admin_update_resource_status'),

    # ============ BOOKING MANAGEMENT ============
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('bookings/<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('bookings/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('my-bookings/export/', views.export_bookings, name='export_bookings'),
    path('bookings/<int:booking_id>/export-pdf/', views.export_single_booking_pdf, name='export_single_booking_pdf'),
    path('bookings/<int:booking_id>/export-html/', views.export_single_booking_html, name='export_single_booking_html'),

    # ============ USER PROFILE ============
    path('profile/', views.profile, name='profile'),
    path('profile/<int:user_id>/', views.profile, name='profile_detail'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('booking-history/', views.booking_history, name='booking_history'),
    
    # ============ EQUIPMENT RENTAL SYSTEM ============
    path('equipment/', views.equipment_list, name='equipment_list'),
    path('equipment/search/', views.equipment_search, name='equipment_search'),
    path('equipment/search/suggest/', views.search_suggestions, name='search_suggestions'),
    path('equipment/<int:equipment_id>/', views.equipment_detail, name='equipment_detail'),
    path('equipment-dashboard/', views.equipment_dashboard, name='equipment_dashboard'),
    
    path('my-equipment/', views.my_equipment, name='my_equipment'),
    path('equipment/create/', views.create_equipment, name='create_equipment'),
    path('equipment/<int:equipment_id>/edit/', views.edit_equipment, name='edit_equipment'),
    path('equipment/<int:equipment_id>/delete/', views.delete_equipment, name='delete_equipment'),
    
    # ============ EQUIPMENT GALLERY ============
    path('equipment/<int:equipment_id>/gallery/', views.equipment_gallery, name='equipment_gallery'),
    path('equipment/gallery/<int:image_id>/delete/', views.delete_gallery_image, name='delete_gallery_image'),
    path('equipment/gallery/<int:image_id>/set-primary/', views.set_primary_gallery_image, name='set_primary_gallery_image'),
    path('equipment/<int:equipment_id>/reorder/', views.reorder_gallery_images, name='reorder_gallery_images'),
    
    path('my-rentals/', views.my_rentals, name='my_rentals'),
    path('rentals/<int:rental_id>/', views.rental_detail, name='rental_detail'),
    path('equipment/rent/', views.rent_equipment, name='rent_equipment'),
    path('equipment/return/', views.return_equipment, name='return_equipment'),
    
    path('equipment-maintenance/', views.equipment_maintenance, name='equipment_maintenance'),
    path('equipment-maintenance/complete/', views.complete_maintenance, name='complete_maintenance'),
    path('equipment-maintenance/<int:maintenance_id>/', views.maintenance_detail, name='maintenance_detail'),

    # ============ SEARCH & EXPORT ============
    path('equipment/search/save/', views.save_search, name='save_search'),
    path('equipment/search/saved/', views.get_saved_searches, name='get_saved_searches'),
    path('equipment/search/saved/<int:search_id>/delete/', views.delete_saved_search, name='delete_saved_search'),
    path('equipment/search/saved/<int:search_id>/favorite/', views.toggle_search_favorite, name='toggle_search_favorite'),
    path('equipment/search/export/', views.export_search_results, name='export_search_results'),
    
    # ============ CALENDAR VIEW ============
    path('calendar/', views.CalendarView.as_view(), name='calendar_view'),

    # ============ REVIEWS ============
    path('resources/<int:resource_id>/reviews/', views.resource_reviews, name='resource_reviews'),
    path('resources/<int:resource_id>/write-review/', views.write_review, name='write_review'),
    path('my-reviews/', views.my_reviews, name='my_reviews'),
    path('my-review-history/', views.my_review_history, name='my_review_history'),
    path('reviews/<int:review_id>/edit/', views.edit_review, name='edit_review'),
    path('reviews/<int:review_id>/delete/', views.delete_review, name='delete_review'),

    # ============ ADMIN REVIEW MANAGEMENT ============
    path('reviews-admin/', views.admin_reviews, name='admin_reviews'),
    path('reviews-admin/<int:review_id>/', views.admin_review_detail, name='admin_review_detail'),
    path('reviews-admin/bulk-action/', views.admin_bulk_action_reviews, name='admin_bulk_action_reviews'),

    # ============ EQUIPMENT RESERVATIONS ============
    path('reservations/', views.reservation_list, name='reservation_list'),
    path('reservations/create/', views.create_reservation, name='create_reservation'),
    path('reservations/<int:reservation_id>/', views.reservation_detail, name='reservation_detail'),
    path('reservations/<int:reservation_id>/cancel/', views.cancel_reservation_view, name='cancel_reservation'),
    path('reservations/<int:reservation_id>/confirm/', views.confirm_reservation_view, name='confirm_reservation'),
    path('reservations/calendar/', views.reservation_calendar, name='reservation_calendar'),

    # ============ ANALYTICS ============
    path('analytics/', views.admin_dashboard, name='admin_dashboard'),
    path('analytics/data/', views.analytics_data, name='analytics_data'),
    path('analytics/export/', views.export_report, name='export_report'),

    # ============ API ENDPOINTS ============
    path('api/available-times/', views.get_available_times, name='get_available_times'),
    path('api/available-equipment/', views.get_available_equipment_ajax, name='get_available_equipment'),
    path('api/book/', views.book_slot, name='book_slot'),
    path('api/reviews/<int:review_id>/helpful/', views.toggle_review_helpful, name='toggle_review_helpful'),

]