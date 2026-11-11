import calendar
import datetime
from typing import Any, Dict, List, Optional, Tuple
from rest_framework.exceptions import NotFound, ValidationError
from core.database import db, now_utc, id_query, to_object_id
from core.helpers import DistanceHelper, geocode_address
from core.serializers import format_order


def parse_date_query(date_str: str) -> Dict[str, Any]:
    """Builds a query filter that matches both datetime/date objects and strings."""
    try:
        dt = datetime.datetime.strptime(date_str[:10], '%Y-%m-%d')
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return {
            '$or': [
                {'delivery_date': {'$gte': start, '$lte': end}},
                {'delivery_date': {'$regex': f"^{date_str[:10]}"}},
                {'delivery_date': date_str[:10]},
            ]
        }
    except Exception:
        return {'delivery_date': date_str}


def resolve_nearest_center(user_id: str, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    centers = list(db.delivery_centers.find({'user_id': str(user_id)}))
    if not centers:
        return None

    nearest = None
    min_dist = 10.0  # strict 10km radius

    for c in centers:
        dist = DistanceHelper.km_between(latitude, longitude, float(c['latitude']), float(c['longitude']))
        if dist <= min_dist:
            min_dist = dist
            nearest = c

    return nearest


def list_orders_paginated(
    user_id: str,
    page: int = 1,
    per_page: int = 15,
    status_filter: Optional[str] = None,
    date_filter: Optional[str] = None,
    delivery_center_id: Optional[str] = None,
    base_url: str = '',
) -> Dict[str, Any]:
    q: Dict[str, Any] = {'user_id': str(user_id)}

    if status_filter:
        q['status'] = str(status_filter).lower()

    if date_filter:
        dq = parse_date_query(date_filter)
        q.update(dq)

    if delivery_center_id:
        dc_str = str(delivery_center_id)
        q['$or'] = [
            {'delivery_center_id': dc_str},
            {'delivery_center_id': to_object_id(dc_str)}
        ]

    total = db.orders.count_documents(q)
    skip = (page - 1) * per_page
    last_page = max(1, (total + per_page - 1) // per_page) if total > 0 else 1

    docs = list(db.orders.find(q).sort('_id', -1).skip(skip).limit(per_page))
    data = [format_order(d) for d in docs]

    from_idx = skip + 1 if total > 0 and len(data) > 0 else None
    to_idx = skip + len(data) if total > 0 and len(data) > 0 else None

    links = {
        'first': f"{base_url}?page=1" if base_url else None,
        'last': f"{base_url}?page={last_page}" if base_url else None,
        'prev': f"{base_url}?page={page - 1}" if page > 1 and base_url else None,
        'next': f"{base_url}?page={page + 1}" if page < last_page and base_url else None,
    }

    meta = {
        'current_page': page,
        'from': from_idx,
        'last_page': last_page,
        'links': [
            {'url': links['prev'], 'label': '&laquo; Previous', 'active': False},
            {'url': f"{base_url}?page={page}" if base_url else None, 'label': str(page), 'active': True},
            {'url': links['next'], 'label': 'Next &raquo;', 'active': False},
        ],
        'path': base_url,
        'per_page': per_page,
        'to': to_idx,
        'total': total,
    }

    return {
        'data': data,
        'links': links,
        'meta': meta,
    }


def create_order(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    address = data.get('address')
    delivery_date = data.get('delivery_date')
    priority = data.get('priority', 'normal')
    lat = data.get('latitude')
    lng = data.get('longitude')

    errors = {}
    if not address:
        errors['address'] = ['The address field is required.']
    if not delivery_date:
        errors['delivery_date'] = ['The delivery date field is required.']

    if priority and str(priority).lower() not in ('normal', 'priority'):
        errors['priority'] = ['The selected priority is invalid.']

    if errors:
        raise ValidationError(errors)

    # Internal geocoding if lat/lng not provided
    if lat is None or lng is None:
        geo = geocode_address(address)
        lat = geo['lat']
        lng = geo['lng']
    else:
        try:
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError):
            raise ValidationError({'latitude': ['Coordinates must be numbers.']})

    center = resolve_nearest_center(user_id, lat, lng)
    
    order_doc = {
        'user_id': str(user_id),
        'address': str(address).strip(),
        'latitude': lat,
        'longitude': lng,
        'delivery_date': delivery_date,
        'delivery_center_id': str(center['_id']) if center else None,
        'vehicle_id': None,
        'status': 'assigned' if center else 'pending',
        'priority': str(priority).lower() if priority else 'normal',
        'created_at': now_utc(),
        'updated_at': now_utc(),
    }

    res = db.orders.insert_one(order_doc)
    order_doc['_id'] = res.inserted_id
    return order_doc


def find_order(user_id: str, order_id: str) -> Optional[Dict[str, Any]]:
    q = id_query(order_id)
    q['user_id'] = str(user_id)
    return db.orders.find_one(q)


def update_order(user_id: str, order_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    order = find_order(user_id, order_id)
    if not order:
        raise NotFound('Order not found.')

    updates: Dict[str, Any] = {}

    if 'status' in data:
        st = str(data['status']).lower()
        if st not in ('pending', 'assigned', 'delivered'):
            raise ValidationError({'status': ['The selected status is invalid.']})
        updates['status'] = st

    if 'priority' in data:
        pr = str(data['priority']).lower()
        if pr not in ('normal', 'priority'):
            raise ValidationError({'priority': ['The selected priority is invalid.']})
        updates['priority'] = pr

    if 'vehicle_id' in data:
        v_id = data['vehicle_id']
        if v_id:
            vehicle_q = id_query(v_id)
            vehicle_q['user_id'] = str(user_id)
            vehicle = db.vehicles.find_one(vehicle_q)
            if not vehicle:
                raise ValidationError({'vehicle_id': ['Vehicle not found.']})

            order_dc_id = str(order.get('delivery_center_id', ''))
            vehicle_dc_id = str(vehicle.get('delivery_center_id', ''))
            if vehicle_dc_id != order_dc_id:
                raise ValidationError({
                    'vehicle_id': ["This vehicle does not belong to the order's delivery center."]
                })
            updates['vehicle_id'] = str(vehicle['_id'])
        else:
            updates['vehicle_id'] = None

    if updates:
        updates['updated_at'] = now_utc()
        db.orders.update_one({'_id': order['_id']}, {'$set': updates})
        order.update(updates)

    return order


def assign_order(user_id: str, order_id: str) -> Dict[str, Any]:
    order = find_order(user_id, order_id)
    if not order:
        raise NotFound('Order not found.')

    lat = float(order.get('latitude', 0.0))
    lng = float(order.get('longitude', 0.0))

    center = resolve_nearest_center(user_id, lat, lng)
    if not center:
        raise ValidationError({
            'address': {
                'message': 'No nearby delivery center found within 10km.',
                'code': 'out_of_range',
            }
        })

    updates = {
        'delivery_center_id': str(center['_id']),
        'status': 'assigned',
        'updated_at': now_utc(),
    }
    db.orders.update_one({'_id': order['_id']}, {'$set': updates})
    order.update(updates)
    return order


def delete_order(user_id: str, order_id: str) -> None:
    order = find_order(user_id, order_id)
    if order:
        db.orders.delete_one({'_id': order['_id']})


def get_date_counts(user_id: str, year: int, month: int) -> Dict[str, int]:
    num_days = calendar.monthrange(year, month)[1]
    start = datetime.datetime(year, month, 1, 0, 0, 0)
    end = datetime.datetime(year, month, num_days, 23, 59, 59, 999999)
    prefix = f"{year:04d}-{month:02d}"

    orders = list(db.orders.find({
        'user_id': str(user_id),
        '$or': [
            {'delivery_date': {'$gte': start, '$lte': end}},
            {'delivery_date': {'$regex': f"^{prefix}"}},
        ]
    }))

    counts: Dict[str, int] = {}
    for o in orders:
        d = o.get('delivery_date')
        if hasattr(d, 'strftime'):
            ds = d.strftime('%Y-%m-%d')
        elif isinstance(d, str):
            ds = d[:10]
        else:
            continue
        counts[ds] = counts.get(ds, 0) + 1

    return counts


def get_bulk_counts(user_id: str, date: Optional[str] = None) -> Dict[str, int]:
    q: Dict[str, Any] = {'user_id': str(user_id)}
    if date:
        q.update(parse_date_query(date))

    total = db.orders.count_documents(q)
    
    q_completed = dict(q)
    q_completed['status'] = 'delivered'
    completed = db.orders.count_documents(q_completed)

    q_pending = dict(q)
    q_pending['status'] = 'pending'
    pending = db.orders.count_documents(q_pending)

    return {
        'completed': completed,
        'pending': pending,
        'total': total,
    }


def clear_orders_by_date(user_id: str, date: Optional[str]) -> int:
    if not date:
        raise ValidationError({'date': ['Date parameter is required.']})

    q: Dict[str, Any] = {'user_id': str(user_id)}
    q.update(parse_date_query(date))
    res = db.orders.delete_many(q)
    return res.deleted_count


def delete_completed_orders(user_id: str, date: Optional[str] = None) -> int:
    q: Dict[str, Any] = {'user_id': str(user_id), 'status': 'delivered'}
    if date:
        q.update(parse_date_query(date))
    res = db.orders.delete_many(q)
    return res.deleted_count


def delete_pending_orders(user_id: str, date: Optional[str] = None) -> int:
    q: Dict[str, Any] = {'user_id': str(user_id), 'status': 'pending'}
    if date:
        q.update(parse_date_query(date))
    res = db.orders.delete_many(q)
    return res.deleted_count


def delete_all_orders(user_id: str, date: Optional[str] = None) -> int:
    q: Dict[str, Any] = {'user_id': str(user_id)}
    if date:
        q.update(parse_date_query(date))
    res = db.orders.delete_many(q)
    return res.deleted_count


def mark_all_delivered(user_id: str, date: Optional[str] = None) -> int:
    q: Dict[str, Any] = {
        'user_id': str(user_id),
        'status': {'$in': ['pending', 'assigned']}
    }
    if date:
        q.update(parse_date_query(date))

    count = db.orders.count_documents(q)
    db.orders.update_many(q, {'$set': {'status': 'delivered', 'updated_at': now_utc()}})
    return count
