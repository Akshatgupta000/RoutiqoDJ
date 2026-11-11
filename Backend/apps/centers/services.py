from typing import Any, Dict, List, Optional
from rest_framework.exceptions import NotFound, ValidationError
from core.helpers import DistanceHelper
from core.serializers import format_delivery_center
from apps.centers.models import DeliveryCenter
from apps.orders.models import Order
from apps.vehicles.models import Vehicle
from apps.zones.models import ServiceZone
from apps.routes.models import Route


def list_centers(user_id: Any) -> List[DeliveryCenter]:
    return list(DeliveryCenter.objects.filter(user_id=user_id).order_by('name'))


def find_center(user_id: Any, center_id: Any) -> Optional[DeliveryCenter]:
    try:
        return DeliveryCenter.objects.filter(id=center_id, user_id=user_id).first()
    except (ValueError, TypeError):
        return None


def reassign_orders_to_best_center(user_id: Any, orders: Optional[List[Order]] = None) -> None:
    centers = list_centers(user_id)

    if orders is None:
        orders = list(Order.objects.filter(user_id=user_id))

    if not centers:
        Order.objects.filter(user_id=user_id, id__in=[o.id for o in orders]).update(
            delivery_center=None,
            status=Order.STATUS_PENDING
        )
        return

    orders_to_update = []
    for order in orders:
        order_lat = float(order.latitude)
        order_lon = float(order.longitude)
        min_dist = 10.0  # Strict 10km radius
        nearest_center = None

        # Bounding box filter (Approx 0.12 deg ~ 13.3km)
        for center in centers:
            c_lat = float(center.latitude)
            c_lon = float(center.longitude)

            if abs(order_lat - c_lat) > 0.12 or abs(order_lon - c_lon) > 0.12:
                continue

            dist = DistanceHelper.km_between(order_lat, order_lon, c_lat, c_lon)
            if dist <= min_dist:
                min_dist = dist
                nearest_center = center

        if nearest_center:
            order.delivery_center = nearest_center
            order.status = Order.STATUS_ASSIGNED
        else:
            order.delivery_center = None
            order.status = Order.STATUS_PENDING

        orders_to_update.append(order)

    if orders_to_update:
        Order.objects.bulk_update(orders_to_update, ['delivery_center', 'status', 'updated_at'])


def create_center(user_id: Any, data: Dict[str, Any]) -> DeliveryCenter:
    name = data.get('name')
    lat = data.get('latitude')
    lng = data.get('longitude')

    errors = {}
    if not name:
        errors['name'] = ['The name field is required.']
    if lat is None:
        errors['latitude'] = ['The latitude field is required.']
    else:
        try:
            lat = float(lat)
            if not (-90.0 <= lat <= 90.0):
                errors['latitude'] = ['The latitude field must be between -90 and 90.']
        except (ValueError, TypeError):
            errors['latitude'] = ['The latitude field must be a number.']

    if lng is None:
        errors['longitude'] = ['The longitude field is required.']
    else:
        try:
            lng = float(lng)
            if not (-180.0 <= lng <= 180.0):
                errors['longitude'] = ['The longitude field must be between -180 and 180.']
        except (ValueError, TypeError):
            errors['longitude'] = ['The longitude field must be a number.']

    if errors:
        raise ValidationError(errors)

    center = DeliveryCenter.objects.create(
        user_id=user_id,
        name=str(name).strip(),
        latitude=lat,
        longitude=lng,
    )

    # Auto-redistribute orders (New hub captures nearby orders)
    reassign_orders_to_best_center(user_id)

    return center


def update_center(user_id: Any, center_id: Any, data: Dict[str, Any]) -> DeliveryCenter:
    center = find_center(user_id, center_id)
    if not center:
        raise NotFound('Delivery center not found.')

    if 'name' in data:
        center.name = str(data['name']).strip()
    if 'latitude' in data:
        try:
            lat = float(data['latitude'])
            if not (-90.0 <= lat <= 90.0):
                raise ValidationError({'latitude': ['The latitude field must be between -90 and 90.']})
            center.latitude = lat
        except (ValueError, TypeError):
            raise ValidationError({'latitude': ['The latitude field must be a number.']})
    if 'longitude' in data:
        try:
            lng = float(data['longitude'])
            if not (-180.0 <= lng <= 180.0):
                raise ValidationError({'longitude': ['The longitude field must be between -180 and 180.']})
            center.longitude = lng
        except (ValueError, TypeError):
            raise ValidationError({'longitude': ['The longitude field must be a number.']})

    center.save()
    return center


def delete_center(user_id: Any, center_id: Any) -> Dict[str, Any]:
    center = find_center(user_id, center_id)
    if not center:
        raise NotFound('Delivery center not found.')

    # Step 1: Get orders of deleting hub
    orders = list(Order.objects.filter(user_id=user_id, delivery_center=center))

    # Step 2: Delete vehicles of this hub
    Vehicle.objects.filter(user_id=user_id, delivery_center=center).delete()

    # Step 3: Delete service zones of this hub
    ServiceZone.objects.filter(user_id=user_id, delivery_center=center).delete()

    # Step 4: Delete Hub
    center.delete()

    # Step 5: Reassign orphaned orders to remaining hubs
    reassign_orders_to_best_center(user_id, orders)

    # Step 6: Clear ALL routes to reset map as requested
    Route.objects.filter(user_id=user_id).delete()

    remaining_centers = list_centers(user_id)
    return {
        'message': 'Hub deleted and orders reassigned',
        'centers': [format_delivery_center(c) for c in remaining_centers],
    }
