from typing import Any, Dict, List, Optional
from rest_framework.exceptions import NotFound, ValidationError
from core.database import db, now_utc, id_query, to_object_id
from core.helpers import DistanceHelper
from core.serializers import format_delivery_center


def list_centers(user_id: str) -> List[Dict[str, Any]]:
    docs = list(db.delivery_centers.find({'user_id': str(user_id)}).sort('name', 1))
    return docs


def find_center(user_id: str, center_id: str) -> Optional[Dict[str, Any]]:
    q = id_query(center_id)
    q['user_id'] = str(user_id)
    return db.delivery_centers.find_one(q)


def reassign_orders_to_best_center(user_id: str, orders: Optional[List[Dict[str, Any]]] = None) -> None:
    centers = list_centers(user_id)
    
    if orders is None:
        orders = list(db.orders.find({'user_id': str(user_id)}))

    if not centers:
        for order in orders:
            db.orders.update_one(
                {'_id': order['_id']},
                {'$set': {'delivery_center_id': None, 'status': 'pending', 'updated_at': now_utc()}}
            )
        return

    for order in orders:
        order_lat = float(order.get('latitude', 0.0))
        order_lon = float(order.get('longitude', 0.0))
        min_dist = 10.0  # Strict 10km radius
        nearest_center = None

        # Bounding box filter (Approx 0.12 deg ~ 13.3km)
        for center in centers:
            c_lat = float(center.get('latitude', 0.0))
            c_lon = float(center.get('longitude', 0.0))

            if abs(order_lat - c_lat) > 0.12 or abs(order_lon - c_lon) > 0.12:
                continue

            dist = DistanceHelper.km_between(order_lat, order_lon, c_lat, c_lon)
            if dist <= min_dist:
                min_dist = dist
                nearest_center = center

        if nearest_center:
            db.orders.update_one(
                {'_id': order['_id']},
                {
                    '$set': {
                        'delivery_center_id': str(nearest_center['_id']),
                        'status': 'assigned',
                        'updated_at': now_utc(),
                    }
                }
            )
        else:
            db.orders.update_one(
                {'_id': order['_id']},
                {
                    '$set': {
                        'delivery_center_id': None,
                        'status': 'pending',
                        'updated_at': now_utc(),
                    }
                }
            )


def create_center(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
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

    center_doc = {
        'user_id': str(user_id),
        'name': str(name).strip(),
        'latitude': float(lat),
        'longitude': float(lng),
        'created_at': now_utc(),
        'updated_at': now_utc(),
    }
    res = db.delivery_centers.insert_one(center_doc)
    center_doc['_id'] = res.inserted_id

    # Auto-redistribute orders (New hub captures nearby orders)
    reassign_orders_to_best_center(user_id)

    return center_doc


def update_center(user_id: str, center_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    center = find_center(user_id, center_id)
    if not center:
        raise NotFound('Delivery center not found.')

    updates: Dict[str, Any] = {}
    if 'name' in data:
        updates['name'] = str(data['name']).strip()
    if 'latitude' in data:
        try:
            lat = float(data['latitude'])
            if not (-90.0 <= lat <= 90.0):
                raise ValidationError({'latitude': ['The latitude field must be between -90 and 90.']})
            updates['latitude'] = lat
        except (ValueError, TypeError):
            raise ValidationError({'latitude': ['The latitude field must be a number.']})
    if 'longitude' in data:
        try:
            lng = float(data['longitude'])
            if not (-180.0 <= lng <= 180.0):
                raise ValidationError({'longitude': ['The longitude field must be between -180 and 180.']})
            updates['longitude'] = lng
        except (ValueError, TypeError):
            raise ValidationError({'longitude': ['The longitude field must be a number.']})

    if updates:
        updates['updated_at'] = now_utc()
        db.delivery_centers.update_one({'_id': center['_id']}, {'$set': updates})
        center.update(updates)

    return center


def delete_center(user_id: str, center_id: str) -> Dict[str, Any]:
    center = find_center(user_id, center_id)
    if not center:
        raise NotFound('Delivery center not found.')

    c_id_str = str(center['_id'])

    # Step 1: Get orders of deleting hub
    orders = list(db.orders.find({
        'user_id': str(user_id),
        '$or': [{'delivery_center_id': c_id_str}, {'delivery_center_id': to_object_id(c_id_str)}]
    }))

    # Step 2: Delete vehicles of this hub
    db.vehicles.delete_many({
        'user_id': str(user_id),
        '$or': [{'delivery_center_id': c_id_str}, {'delivery_center_id': to_object_id(c_id_str)}]
    })

    # Step 3: Delete service zones of this hub
    db.service_zones.delete_many({
        'user_id': str(user_id),
        '$or': [{'delivery_center_id': c_id_str}, {'delivery_center_id': to_object_id(c_id_str)}]
    })

    # Step 4: Delete Hub
    db.delivery_centers.delete_one({'_id': center['_id']})

    # Step 5: Reassign orphaned orders to remaining hubs
    reassign_orders_to_best_center(user_id, orders)

    # Step 6: Clear ALL routes to reset map as requested
    db.routes.delete_many({'user_id': str(user_id)})

    remaining_centers = list_centers(user_id)
    return {
        'message': 'Hub deleted and orders reassigned',
        'centers': [format_delivery_center(c) for c in remaining_centers],
    }
