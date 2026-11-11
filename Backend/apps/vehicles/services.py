from typing import Any, Dict, List, Optional
from rest_framework.exceptions import NotFound, ValidationError
from core.database import db, now_utc, id_query, to_object_id
from core.helpers import VehicleHelper
from core.serializers import format_vehicle


def list_vehicles(user_id: str, delivery_center_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {'user_id': str(user_id)}
    if delivery_center_id is not None:
        dc_str = str(delivery_center_id)
        q['$or'] = [
            {'delivery_center_id': dc_str},
            {'delivery_center_id': to_object_id(dc_str)},
            {'delivery_center_id': None},
        ]
    return list(db.vehicles.find(q).sort('_id', 1))


def find_vehicle(user_id: str, vehicle_id: str) -> Optional[Dict[str, Any]]:
    q = id_query(vehicle_id)
    q['user_id'] = str(user_id)
    return db.vehicles.find_one(q)


def create_vehicle(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
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

    # Resolve center to generate RTO prefix
    center_query = id_query(dc_id)
    center_query['user_id'] = str(user_id)
    center = db.delivery_centers.find_one(center_query)
    
    if center:
        prefix = VehicleHelper.get_rto_prefix_from_center_name(center.get('name', ''))
        vehicle_number = VehicleHelper.generate_indian_vehicle_number(prefix)
    else:
        vehicle_number = VehicleHelper.generate_indian_vehicle_number()

    vehicle_doc = {
        'user_id': str(user_id),
        'name': str(name).strip(),
        'vehicle_number': vehicle_number,
        'capacity': int(capacity),
        'current_load': 0,
        'average_speed': float(average_speed),
        'is_available': bool(is_available),
        'delivery_center_id': str(center['_id']) if center else str(dc_id),
        'created_at': now_utc(),
        'updated_at': now_utc(),
    }

    res = db.vehicles.insert_one(vehicle_doc)
    vehicle_doc['_id'] = res.inserted_id
    return vehicle_doc


def update_vehicle(user_id: str, vehicle_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    vehicle = find_vehicle(user_id, vehicle_id)
    if not vehicle:
        raise NotFound('Vehicle not found.')

    updates: Dict[str, Any] = {}
    if 'name' in data:
        updates['name'] = str(data['name']).strip()
    if 'capacity' in data:
        try:
            cap = int(data['capacity'])
            if not (1 <= cap <= 1000):
                raise ValidationError({'capacity': ['The capacity field must be between 1 and 1000.']})
            updates['capacity'] = cap
        except (ValueError, TypeError):
            raise ValidationError({'capacity': ['The capacity field must be an integer.']})

    if 'average_speed' in data:
        try:
            speed = float(data['average_speed'])
            if not (1.0 <= speed <= 200.0):
                raise ValidationError({'average_speed': ['The average speed field must be between 1 and 200.']})
            updates['average_speed'] = speed
        except (ValueError, TypeError):
            raise ValidationError({'average_speed': ['The average speed field must be a number.']})

    if 'is_available' in data:
        updates['is_available'] = bool(data['is_available'])

    if 'delivery_center_id' in data:
        updates['delivery_center_id'] = str(data['delivery_center_id'])

    if updates:
        updates['updated_at'] = now_utc()
        db.vehicles.update_one({'_id': vehicle['_id']}, {'$set': updates})
        vehicle.update(updates)

    return vehicle


def reset_fleet(user_id: str, delivery_center_id: Optional[str] = None) -> Dict[str, str]:
    v_query: Dict[str, Any] = {'user_id': str(user_id)}
    r_query: Dict[str, Any] = {
        'user_id': str(user_id),
        'status': {'$in': ['planned', 'in_progress']}
    }

    if delivery_center_id:
        dc_str = str(delivery_center_id)
        v_query['$or'] = [{'delivery_center_id': dc_str}, {'delivery_center_id': to_object_id(dc_str)}]
        r_query['$or'] = [{'delivery_center_id': dc_str}, {'delivery_center_id': to_object_id(dc_str)}]

    # Reset vehicles
    db.vehicles.update_many(v_query, {'$set': {'is_available': True, 'current_load': 0, 'updated_at': now_utc()}})

    # Find planned/in_progress routes to reset
    routes = list(db.routes.find(r_query))
    for route in routes:
        r_id = str(route['_id'])
        # Find order IDs in this route's stops
        stops = list(db.route_stops.find({'route_id': r_id}))
        order_ids = [s.get('order_id') for s in stops if s.get('order_id')]

        if order_ids:
            db.orders.update_many(
                {
                    'user_id': str(user_id),
                    '$or': [
                        {'_id': {'$in': [to_object_id(oid) for oid in order_ids]}},
                        {'_id': {'$in': [str(oid) for oid in order_ids]}},
                    ]
                },
                {'$set': {'vehicle_id': None, 'updated_at': now_utc()}}
            )

        # Delete route and stops
        db.route_stops.delete_many({'route_id': r_id})
        db.routes.delete_one({'_id': route['_id']})

    return {'message': 'Fleet and active routes reset successful'}


def delete_vehicle(user_id: str, vehicle_id: str) -> None:
    vehicle = find_vehicle(user_id, vehicle_id)
    if not vehicle:
        return

    v_id_str = str(vehicle['_id'])

    # Delete planned routes for vehicle to avoid orphan routes
    planned_routes = list(db.routes.find({
        'user_id': str(user_id),
        'status': 'planned',
        '$or': [{'vehicle_id': v_id_str}, {'vehicle_id': to_object_id(v_id_str)}]
    }))
    for r in planned_routes:
        db.route_stops.delete_many({'route_id': str(r['_id'])})
        db.routes.delete_one({'_id': r['_id']})

    db.vehicles.delete_one({'_id': vehicle['_id']})
