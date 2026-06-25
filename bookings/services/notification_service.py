from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

class NotificationService:
    
    @staticmethod
    def send_reservation_confirmed(reservation):
        """Send email when reservation is confirmed"""
        subject = f'Reservation Confirmed: {reservation.equipment.name}'
        message = f"""
        Hello {reservation.user.username},
        
        Your reservation has been CONFIRMED!
        
        Reservation Details:
        Equipment: {reservation.equipment.name}
        Serial Number: {reservation.equipment.serial_number}
        Start Date: {reservation.start_date.strftime('%B %d, %Y at %H:%M')}
        End Date: {reservation.end_date.strftime('%B %d, %Y at %H:%M')}
        Location: {reservation.equipment.location or 'Not specified'}
        
        Your reservation is now confirmed and secured.
        
        View your reservation: /reservations/{reservation.id}/
        
        Thank you for using our equipment rental service!
        """
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [reservation.user.email])
    
    @staticmethod
    def send_reservation_cancelled(reservation):
        """Send email when reservation is cancelled"""
        subject = f'Reservation Cancelled: {reservation.equipment.name}'
        message = f"""
        Hello {reservation.user.username},
        
        Your reservation has been CANCELLED.
        
        Reservation Details:
        Equipment: {reservation.equipment.name}
        Serial Number: {reservation.equipment.serial_number}
        Original Start: {reservation.start_date.strftime('%B %d, %Y at %H:%M')}
        Original End: {reservation.end_date.strftime('%B %d, %Y at %H:%M')}
        
        If you didn't request this cancellation, please contact support.
        """
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [reservation.user.email])
    
    @staticmethod
    def send_reservation_created(reservation):
        """Send email when reservation is created"""
        subject = f'Reservation Created: {reservation.equipment.name}'
        message = f"""
        Hello {reservation.user.username},
        
        Your reservation has been created and is pending approval.
        
        Reservation Details:
        Equipment: {reservation.equipment.name}
        Serial Number: {reservation.equipment.serial_number}
        Start Date: {reservation.start_date.strftime('%B %d, %Y at %H:%M')}
        End Date: {reservation.end_date.strftime('%B %d, %Y at %H:%M')}
        
        Status: PENDING (awaiting staff confirmation)
        This reservation will expire in 24 hours if not confirmed.
        
        View your reservation: /reservations/{reservation.id}/
        """
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [reservation.user.email])
    
    @staticmethod
    def send_reservation_reminder(reservation):
        """Send reminder 24 hours before reservation starts"""
        subject = f'Reminder: {reservation.equipment.name} Reservation Tomorrow'
        message = f"""
        Hello {reservation.user.username},
        
        This is a reminder that your equipment reservation starts tomorrow!
        
        Reservation Details:
        Equipment: {reservation.equipment.name}
        Serial Number: {reservation.equipment.serial_number}
        Start Date: {reservation.start_date.strftime('%B %d, %Y at %H:%M')}
        Location: {reservation.equipment.location or 'Not specified'}
        
        Please arrive on time to collect your equipment.
        """
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [reservation.user.email])