from django.db import models
from django.conf import settings


class DeliveryCenter(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='delivery_centers'
    )
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'centers_deliverycenter'
        ordering = ['name']
        indexes = [
            models.Index(fields=['user', 'name']),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

