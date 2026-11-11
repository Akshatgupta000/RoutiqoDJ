from typing import Any, Dict, List, Optional
from django.db.models import Q
from rest_framework.exceptions import NotFound, ValidationError
from core.helpers import VehicleHelper
from apps.vehicles.models import Vehicle
from apps.centers.models import DeliveryCenter
from apps.routes.models import Route, RouteStop
from apps.orders.models import Order


def list_vehicles(user_id: Any, delivery_center_id: Optional[Any] = None) -> List[Vehicle]:
    q = Vehicle.objects.filter(user_id=user_id)
    if delivery_center_id is not None:
        try:
            q = q.filter(Q(delivery_center_id=delivery_center_id) | Q(delivery_center__isnull=True))
        except (ValueError, TypeError):
            pass
    return list(q.order_by('id'))


def find_vehicle(user_id: Any, vehicle_id: Any) -> Optional[Vehicle]:
    try:
        return Vehicle.objects.filter(id=vehicle_id, user_id=user_id).first()
    except (ValueError, TypeError):
        return None


def create_vehicle(user_id: Any, data: Dict[str, Any]) -> Vehicle:
    name = data.get('name')
    capacity = data.get('capacity')
    average_speed = data.get('average_speed', 25.0)
    is_available = data.get('is_available', True)
    dc_id = data.get('delivery_center_id')

    errors = {}
    if not name:
        errors['name'] = ['The name field is required.']
    if capacity is None:
        errors['capacity'] = ['The capacity field is required.']
    else:
        try:
            capacity = int(capacity)
            if not (1 <= capacity <= 1000):
                errors['capacity'] = ['The capacity field must be between 1 and 1000.']
        except (ValueError, TypeError):
            errors['capacity'] = ['The capacity field must be an integer.']

    if not dc_id:
        errors['delivery_center_id'] = ['The delivery center id field is required.']

    if average_speed is not None:
        try:
            average_speed = float(average_speed)
            if not (1.0 <= average_speed <= 200.0):
                errors['average_speed'] = ['The average speed field must be between 1 and 200.']
        except (ValueError, TypeError):
            errors['average_speed'] = ['The average speed field must be a number.']

    if errors:
        raise ValidationError(errors)

    center = None
    try:
        center = DeliveryCenter.objects.filter(id=dc_id, user_id=user_id).first()
    except (ValueError, TypeError):
        pass

    if center:
        prefix = VehicleHelper.get_rto_prefix_from_center_name(center.name)
        vehicle_number = VehicleHelper.generate_indian_vehicle_number(prefix)
    else:
        vehicle_number = VehicleHelper.generate_indian_vehicle_number()

    vehicle = Vehicle.objects.create(
        user_id=user_id,
        name=str(name).strip(),
        vehicle_number=vehicle_number,
        capacity=int(capacity),
        current_load=0,
        average_speed=float(average_speed),
        is_available=bool(is_available),
        delivery_center=center,
    )
    return vehicle


def update_vehicle(user_id: Any, vehicle_id: Any, data: Dict[str, Any]) -> Vehicle:
    vehicle = find_vehicle(user_id, vehicle_id)
    if not vehicle:
        raise NotFound('Vehicle not found.')

    if 'name' in data:
        vehicle.name = str(data['name']).strip()
    if 'capacity' in data:
        try:
            cap = int(data['capacity'])
            if not (1 <= cap <= 1000):
                raise ValidationError({'capacity': ['The capacity field must be between 1 and 1000.']})
            vehicle.capacity = cap
        except (ValueError, TypeError):
            raise ValidationError({'capacity': ['The capacity field must be an integer.']})

    if 'average_speed' in data:
        try:
            speed = float(data['average_speed'])
            if not (1.0 <= speed <= 200.0):
                raise ValidationError({'average_speed': ['The average speed field must be between 1 and 200.']})
            vehicle.average_speed = speed
        except (ValueError, TypeError):
            raise ValidationError({'average_speed': ['The average speed field must be a number.']})

    if 'is_available' in data:
        vehicle.is_available = bool(data['is_available'])

    if 'delivery_center_id' in data:
        new_dc_id = data['delivery_center_id']
        if new_dc_id:
            center = DeliveryCenter.objects.filter(id=new_dc_id, user_id=user_id).first()
            vehicle.delivery_center = center
        else:
            vehicle.delivery_center = None

    vehicle.save()
    return vehicle


def reset_fleet(user_id: Any, delivery_center_id: Optional[Any] = None) -> Dict[str, str]:
    v_query = Vehicle.objects.filter(user_id=user_id)
    r_query = Route.objects.filter(
        user_id=user_id,
        status__in=[Route.STATUS_PLANNED, Route.STATUS_IN_PROGRESS]
    )

    if delivery_center_id:
        v_query = v_query.filter(delivery_center_id=delivery_center_id)
        r_query = r_query.filter(delivery_center_id=delivery_center_id)

    # Reset vehicles
    v_query.update(is_available=True, current_load=0)

    # Find planned/in_progress routes to reset
    routes = list(r_query)
    for route in routes:
        # Unassign vehicles from orders linked to stops
        stops = RouteStop.objects.filter(route=route).exclude(order__isnull=True)
        order_ids = [s.order_id for s in stops]
        if order_ids:
            Order.objects.filter(id__in=order_ids, user_id=user_id).update(vehicle=None)

        route.delete()

    return {'message': 'Fleet and active routes reset successful'}


def delete_vehicle(user_id: Any, vehicle_id: Any) -> None:
    vehicle = find_vehicle(user_id, vehicle_id)
    if not vehicle:
        return

    # Delete planned routes for vehicle to avoid orphan routes
    planned_routes = Route.objects.filter(
        user_id=user_id,
        vehicle=vehicle,
        status=Route.STATUS_PLANNED
    )
    planned_routes.delete()
    vehicle.delete()
