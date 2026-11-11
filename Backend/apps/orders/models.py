from django.db import models
from django.conf import settings


class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ASSIGNED = 'assigned'
    STATUS_DELIVERED = 'delivered'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_DELIVERED, 'Delivered'),
    ]

    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'priority'
    PRIORITY_CHOICES = [
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH, 'Priority'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    delivery_center = models.ForeignKey(
        'centers.DeliveryCenter',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders'
    )
    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders'
    )
    address = models.TextField()
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    delivery_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders_order'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'delivery_date']),
            models.Index(fields=['user', 'delivery_center']),
        ]

    def __str__(self) -> str:
        return f"Order #{self.id} ({self.status}) - {self.address[:30]}"

