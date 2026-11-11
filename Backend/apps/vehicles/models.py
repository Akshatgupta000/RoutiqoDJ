from django.db import models
from django.conf import settings


class Vehicle(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vehicles'
    )
    delivery_center = models.ForeignKey(
        'centers.DeliveryCenter',
        on_delete=models.CASCADE,
        related_name='vehicles',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=255)
    vehicle_number = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField()
    current_load = models.PositiveIntegerField(default=0)
    average_speed = models.DecimalField(max_digits=6, decimal_places=2, default=25.0)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vehicles_vehicle'
        ordering = ['id']
        indexes = [
            models.Index(fields=['user', 'delivery_center']),
            models.Index(fields=['user', 'is_available']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacity__gte=1) & models.Q(capacity__lte=1000),
                name='vehicle_capacity_range'
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.vehicle_number} ({self.id})"
