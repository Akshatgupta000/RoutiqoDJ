from django.db import models
from django.conf import settings


class ServiceZone(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='service_zones'
    )
    delivery_center = models.ForeignKey(
        'centers.DeliveryCenter',
        on_delete=models.CASCADE,
        related_name='service_zones'
    )
    polygon_coordinates = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'zones_servicezone'
        ordering = ['id']
        indexes = [
            models.Index(fields=['user', 'delivery_center']),
        ]

    def __str__(self) -> str:
        return f"Zone #{self.id} for Hub #{self.delivery_center_id}"

