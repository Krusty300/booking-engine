from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import Equipment, EquipmentRental, MaintenanceRecord

class EquipmentService:
    """Service layer for equipment rental operations"""

    @staticmethod
    @transaction.atomic
    def check_out_equipment(equipment_id, user_id, expected_return_date, condition_notes=""):
        """
        Check out equipment to a user
        """
        equipment = Equipment.objects.select_for_update().get(id=equipment_id)
        
        # Validate equipment availability
        if not equipment.is_available():
            raise ValidationError(f"Equipment '{equipment.name}' is not available for checkout")
        
        # Validate return date
        if expected_return_date <= timezone.now():
            raise ValidationError("Expected return date must be in the future")
        
        # Create rental record
        rental = EquipmentRental.objects.create(
            equipment=equipment,
            rented_by_id=user_id,
            expected_return_date=expected_return_date,
            condition_on_checkout=condition_notes,
            status='CHECKED_OUT',
            checked_out_by_id=user_id
        )
        
        # Update equipment status
        equipment.status = 'RENTED'
        equipment.save()
        
        return rental

    @staticmethod
    @transaction.atomic
    def check_in_equipment(rental_id, user_id, condition_notes=""):
        """
        Check in equipment and update equipment status
        """
        rental = EquipmentRental.objects.select_for_update().get(id=rental_id)
        
        if rental.status == 'CHECKED_IN':
            raise ValidationError("This equipment has already been checked in")
        
        # Update rental
        rental.status = 'CHECKED_IN'
        rental.actual_return_date = timezone.now()
        rental.condition_on_return = condition_notes
        rental.checked_in_by_id = user_id
        rental.save()
        
        # Update equipment status
        equipment = rental.equipment
        equipment.status = 'AVAILABLE'
        equipment.save()
        
        return rental

    @staticmethod
    @transaction.atomic
    def schedule_maintenance(equipment_id, maintenance_type, title, description, 
                            scheduled_date, user_id, cost=None, vendor=""):
        """
        Schedule maintenance for equipment
        """
        equipment = Equipment.objects.select_for_update().get(id=equipment_id)
        
        # Don't allow maintenance for equipment that's already in maintenance
        if equipment.status == 'MAINTENANCE':
            raise ValidationError(f"Equipment '{equipment.name}' is already under maintenance")
        
        # Create maintenance record
        maintenance = MaintenanceRecord.objects.create(
            equipment=equipment,
            maintenance_type=maintenance_type,
            status='SCHEDULED',
            title=title,
            description=description,
            scheduled_date=scheduled_date,
            cost=cost,
            performed_by_id=user_id,
            vendor=vendor
        )
        
        # Update equipment status
        equipment.status = 'MAINTENANCE'
        equipment.save()
        
        return maintenance

    @staticmethod
    @transaction.atomic
    def complete_maintenance(maintenance_id, user_id, notes=""):
        """
        Mark maintenance as completed
        """
        maintenance = MaintenanceRecord.objects.select_for_update().get(id=maintenance_id)
        
        if maintenance.status == 'COMPLETED':
            raise ValidationError("This maintenance record is already completed")
        
        maintenance.complete_maintenance()
        maintenance.notes = notes
        maintenance.save()
        
        return maintenance

    @staticmethod
    def get_available_equipment():
        """Get all available equipment"""
        return Equipment.objects.filter(status='AVAILABLE')

    @staticmethod
    def get_user_rentals(user_id, status=None):
        """Get rentals for a specific user"""
        queryset = EquipmentRental.objects.filter(rented_by_id=user_id)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    @staticmethod
    def get_overdue_rentals():
        """Get all overdue rentals"""
        return EquipmentRental.objects.filter(
            status='CHECKED_OUT',
            expected_return_date__lt=timezone.now()
        )