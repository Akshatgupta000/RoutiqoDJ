import calendar
import datetime
from typing import Any, Dict, List, Optional
from rest_framework.exceptions import NotFound, ValidationError
from core.helpers import DistanceHelper, geocode_address
from core.serializers import format_order
from apps.orders.models import Order
from apps.centers.models import DeliveryCenter
from apps.vehicles.models import Vehicle


def parse_date(date_str: Any) -> Optional[datetime.date]:
    if not date_str:
        return None
    if isinstance(date_str, datetime.date):
        return date_str
    if isinstance(date_str, datetime.datetime):
        return date_str.date()
    try:
        return datetime.datetime.strptime(str(date_str)[:10], '%Y-%m-%d').date()
    except Exception:
        return None


def resolve_nearest_center(user_id: Any, latitude: float, longitude: float) -> Optional[DeliveryCenter]:
    centers = list(DeliveryCenter.objects.filter(user_id=user_id))
    if not centers:
        return None

    nearest = None
    min_dist = 10.0  # strict 10km radius

    for c in centers:
        dist = DistanceHelper.km_between(latitude, longitude, float(c.latitude), float(c.longitude))
        if dist <= min_dist:
            min_dist = dist
            nearest = c

    return nearest


def list_orders_paginated(
    user_id: Any,
    page: int = 1,
    per_page: int = 15,
    status_filter: Optional[str] = None,
    date_filter: Optional[str] = None,
    delivery_center_id: Optional[Any] = None,
    base_url: str = '',
) -> Dict[str, Any]:
    qs = Order.objects.filter(user_id=user_id)

    if status_filter:
        qs = qs.filter(status=str(status_filter).lower())

    if date_filter:
        parsed_d = parse_date(date_filter)
        if parsed_d:
            qs = qs.filter(delivery_date=parsed_d)

    if delivery_center_id:
        try:
            qs = qs.filter(delivery_center_id=delivery_center_id)
        except (ValueError, TypeError):
            pass

    total = qs.count()
    skip = (page - 1) * per_page
    last_page = max(1, (total + per_page - 1) // per_page) if total > 0 else 1

    orders = list(qs.select_related('delivery_center', 'vehicle').order_by('-id')[skip: skip + per_page])
    data = [format_order(d) for d in orders]

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


def create_order(user_id: Any, data: Dict[str, Any]) -> Order:
    address = data.get('address')
    delivery_date_raw = data.get('delivery_date')
    priority = data.get('priority', 'normal')
    lat = data.get('latitude')
    lng = data.get('longitude')

    errors = {}
    if not address:
        errors['address'] = ['The address field is required.']
    if not delivery_date_raw:
        errors['delivery_date'] = ['The delivery date field is required.']

    if priority and str(priority).lower() not in ('normal', 'priority'):
        errors['priority'] = ['The selected priority is invalid.']

    if errors:
        raise ValidationError(errors)

    parsed_delivery_date = parse_date(delivery_date_raw)
    if not parsed_delivery_date:
        raise ValidationError({'delivery_date': ['The delivery date must be in YYYY-MM-DD format.']})

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
    order_status = Order.STATUS_ASSIGNED if center else Order.STATUS_PENDING

    order = Order.objects.create(
        user_id=user_id,
        address=str(address).strip(),
        latitude=lat,
        longitude=lng,
        delivery_date=parsed_delivery_date,
        priority=str(priority).lower(),
        status=order_status,
        delivery_center=center,
    )
    return order


def find_order(user_id: Any, order_id: Any) -> Optional[Order]:
    try:
        return Order.objects.filter(id=order_id, user_id=user_id).select_related('delivery_center', 'vehicle').first()
    except (ValueError, TypeError):
        return None


def update_order(user_id: Any, order_id: Any, data: Dict[str, Any]) -> Order:
    order = find_order(user_id, order_id)
    if not order:
        raise NotFound('Order not found.')

    if 'address' in data:
        order.address = str(data['address']).strip()
    if 'latitude' in data:
        try:
            order.latitude = float(data['latitude'])
        except (ValueError, TypeError):
            raise ValidationError({'latitude': ['The latitude field must be a number.']})
    if 'longitude' in data:
        try:
            order.longitude = float(data['longitude'])
        except (ValueError, TypeError):
            raise ValidationError({'longitude': ['The longitude field must be a number.']})
    if 'delivery_date' in data:
        parsed_d = parse_date(data['delivery_date'])
        if parsed_d:
            order.delivery_date = parsed_d
    if 'status' in data:
        order.status = str(data['status']).lower()
    if 'priority' in data:
        order.priority = str(data['priority']).lower()

    if 'vehicle_id' in data:
        v_id = data['vehicle_id']
        if v_id:
            vehicle = Vehicle.objects.filter(id=v_id, user_id=user_id).first()
            if not vehicle:
                raise ValidationError({'vehicle_id': ['Vehicle not found.']})

            order_dc_id = order.delivery_center_id
            vehicle_dc_id = vehicle.delivery_center_id
            if vehicle_dc_id != order_dc_id:
                raise ValidationError({
                    'vehicle_id': ["This vehicle does not belong to the order's delivery center."]
                })
            order.vehicle = vehicle
        else:
            order.vehicle = None

    order.save()
    return order


def assign_order(user_id: Any, order_id: Any) -> Order:
    order = find_order(user_id, order_id)
    if not order:
        raise NotFound('Order not found.')

    lat = float(order.latitude)
    lng = float(order.longitude)

    center = resolve_nearest_center(user_id, lat, lng)
    if not center:
        raise ValidationError({
            'address': {
                'message': 'No nearby delivery center found within 10km.',
                'code': 'out_of_range',
            }
        })

    order.delivery_center = center
    order.status = Order.STATUS_ASSIGNED
    order.save()
    return order


def delete_order(user_id: Any, order_id: Any) -> None:
    order = find_order(user_id, order_id)
    if order:
        order.delete()


def get_date_counts(user_id: Any, year: int, month: int) -> Dict[str, int]:
    num_days = calendar.monthrange(year, month)[1]
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, num_days)

    orders = Order.objects.filter(
        user_id=user_id,
        delivery_date__gte=start_date,
        delivery_date__lte=end_date
    ).values('delivery_date')

    counts: Dict[str, int] = {}
    for o in orders:
        d = o['delivery_date']
        ds = d.strftime('%Y-%m-%d')
        counts[ds] = counts.get(ds, 0) + 1

    return counts


def get_bulk_counts(user_id: Any, date: Optional[str] = None) -> Dict[str, int]:
    qs = Order.objects.filter(user_id=user_id)
    if date:
        parsed_d = parse_date(date)
        if parsed_d:
            qs = qs.filter(delivery_date=parsed_d)

    total = qs.count()
    completed = qs.filter(status=Order.STATUS_DELIVERED).count()
    pending = qs.filter(status=Order.STATUS_PENDING).count()

    return {
        'completed': completed,
        'pending': pending,
        'total': total,
    }


def clear_orders_by_date(user_id: Any, date: Optional[str]) -> int:
    if not date:
        raise ValidationError({'date': ['Date parameter is required.']})

    parsed_d = parse_date(date)
    if not parsed_d:
        raise ValidationError({'date': ['Invalid date format.']})

    count, _ = Order.objects.filter(user_id=user_id, delivery_date=parsed_d).delete()
    return count


def delete_completed_orders(user_id: Any, date: Optional[str] = None) -> int:
    qs = Order.objects.filter(user_id=user_id, status=Order.STATUS_DELIVERED)
    if date:
        parsed_d = parse_date(date)
        if parsed_d:
            qs = qs.filter(delivery_date=parsed_d)
    count, _ = qs.delete()
    return count


def delete_pending_orders(user_id: Any, date: Optional[str] = None) -> int:
    qs = Order.objects.filter(user_id=user_id, status=Order.STATUS_PENDING)
    if date:
        parsed_d = parse_date(date)
        if parsed_d:
            qs = qs.filter(delivery_date=parsed_d)
    count, _ = qs.delete()
    return count


def delete_all_orders(user_id: Any, date: Optional[str] = None) -> int:
    qs = Order.objects.filter(user_id=user_id)
    if date:
        parsed_d = parse_date(date)
        if parsed_d:
            qs = qs.filter(delivery_date=parsed_d)
    count, _ = qs.delete()
    return count


def mark_all_delivered(user_id: Any, date: Optional[str] = None) -> int:
    qs = Order.objects.filter(
        user_id=user_id,
        status__in=[Order.STATUS_PENDING, Order.STATUS_ASSIGNED]
    )
    if date:
        parsed_d = parse_date(date)
        if parsed_d:
            qs = qs.filter(delivery_date=parsed_d)

    count = qs.update(status=Order.STATUS_DELIVERED)
    return count
