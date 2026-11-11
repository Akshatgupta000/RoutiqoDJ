from django.db import models
from django.conf import settings


class Route(models.Model):
    STATUS_PLANNED = 'planned'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_PLANNED, 'Planned'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='routes'
    )
    delivery_center = models.ForeignKey(
        'centers.DeliveryCenter',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='routes'
    )
    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='routes'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PLANNED,
        db_index=True
    )
    profile = models.CharField(max_length=50, default='shortest_distance')
    comparison_batch_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    total_distance_km = models.DecimalField(max_digits=10, decimal_places=3, default=0.0)
    total_duration_min = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    total_stops = models.PositiveIntegerField(default=0)
    geometry = models.JSONField(default=list)
    departure_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'routes_route'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'delivery_center']),
            models.Index(fields=['comparison_batch_id']),
        ]

    def __str__(self) -> str:
        return f"Route #{self.id} ({self.status}) - Vehicle {self.vehicle_id}"


class RouteStop(models.Model):
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='stops'
    )
    order = models.ForeignKey(
        'orders.Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='route_stops'
    )
    stop_index = models.PositiveIntegerField()
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    address = models.TextField(blank=True, default='')
    eta = models.DateTimeField(null=True, blank=True)
    distance_from_prev_km = models.DecimalField(max_digits=8, decimal_places=3, default=0.0)

    class Meta:
        db_table = 'routes_routestop'
        ordering = ['stop_index']
        unique_together = [['route', 'stop_index']]
        indexes = [
            models.Index(fields=['route', 'stop_index']),
        ]

    def __str__(self) -> str:
        return f"Stop #{self.stop_index} on Route #{self.route_id}"

