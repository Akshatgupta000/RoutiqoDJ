import re
from typing import Any, Dict, List, Optional


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def format_delivery_center(center: Any) -> Optional[Dict[str, Any]]:
    if not center:
        return None
    c_id = str(_get_val(center, 'id', _get_val(center, '_id', '')))
    return {
        'id': c_id,
        'name': str(_get_val(center, 'name', '')),
        'latitude': float(_get_val(center, 'latitude', 0.0)),
        'longitude': float(_get_val(center, 'longitude', 0.0)),
    }


def format_vehicle(vehicle: Any, load_center: bool = False) -> Optional[Dict[str, Any]]:
    if not vehicle:
        return None
    v_id = str(_get_val(vehicle, 'id', _get_val(vehicle, '_id', '')))
    dc_id = _get_val(vehicle, 'delivery_center_id')
    dc_id_str = str(dc_id) if dc_id is not None else None

    res = {
        'id': v_id,
        'name': str(_get_val(vehicle, 'name', '')),
        'vehicle_number': _get_val(vehicle, 'vehicle_number'),
        'capacity': int(_get_val(vehicle, 'capacity', 0)),
        'current_load': int(_get_val(vehicle, 'current_load', 0)),
        'is_available': bool(_get_val(vehicle, 'is_available', True)),
        'average_speed': float(_get_val(vehicle, 'average_speed', 25.0)),
        'delivery_center_id': dc_id_str,
    }

    if load_center:
        center_obj = _get_val(vehicle, 'delivery_center')
        if center_obj is None and dc_id:
            from apps.centers.models import DeliveryCenter
            center_obj = DeliveryCenter.objects.filter(id=dc_id).first()
        res['delivery_center'] = format_delivery_center(center_obj)

    return res


def format_order(order: Any, load_relations: bool = True) -> Optional[Dict[str, Any]]:
    if not order:
        return None
    o_id = str(_get_val(order, 'id', _get_val(order, '_id', '')))
    dc_id = _get_val(order, 'delivery_center_id')
    v_id = _get_val(order, 'vehicle_id')

    delivery_date = _get_val(order, 'delivery_date')
    if hasattr(delivery_date, 'strftime'):
        date_str = delivery_date.strftime('%Y-%m-%d')
    elif isinstance(delivery_date, str):
        date_str = delivery_date[:10]
    else:
        date_str = None

    status = _get_val(order, 'status', 'pending')
    if hasattr(status, 'value'):
        status = status.value

    priority = _get_val(order, 'priority', 'normal')
    if hasattr(priority, 'value'):
        priority = priority.value

    res = {
        'id': o_id,
        'address': str(_get_val(order, 'address', '')),
        'latitude': float(_get_val(order, 'latitude', 0.0)),
        'longitude': float(_get_val(order, 'longitude', 0.0)),
        'delivery_date': date_str,
        'delivery_center_id': str(dc_id) if dc_id is not None else None,
        'vehicle_id': str(v_id) if v_id is not None else None,
        'status': str(status),
        'priority': str(priority),
    }

    if load_relations:
        center_obj = _get_val(order, 'delivery_center')
        if center_obj is None and dc_id:
            from apps.centers.models import DeliveryCenter
            center_obj = DeliveryCenter.objects.filter(id=dc_id).first()
        res['delivery_center'] = format_delivery_center(center_obj)

        vehicle_obj = _get_val(order, 'vehicle')
        if vehicle_obj is None and v_id:
            from apps.vehicles.models import Vehicle
            vehicle_obj = Vehicle.objects.filter(id=v_id).first()
        res['vehicle'] = format_vehicle(vehicle_obj) if vehicle_obj else None

    return res


def compute_route_name(route_id: str, stops: List[Dict[str, Any]]) -> str:
    s_id = str(route_id)
    suffix = s_id[-6:] if len(s_id) >= 6 else s_id
    route_name = f"Route #{suffix}"
    first_stop = stops[0] if stops else None
    if first_stop and first_stop.get('order') and first_stop['order'].get('address'):
        address = first_stop['order']['address']
        address_parts = [p.strip() for p in address.split(',') if p.strip()]

        street = ''
        road_regex = re.compile(
            r'\b(Road|Rd|Street|St|Avenue|Ave|Marg|Highway|Hwy|Lane|Ln|Boulevard|Blvd|Drive|Dr|Way|Square|Sq|Plaza|Parkway|Pkwy|Alley|Court|Ct|Circle|Cir)\b',
            re.IGNORECASE
        )
        for part in address_parts:
            if road_regex.search(part):
                street = part
                break

        if not street:
            if len(address_parts) > 1:
                p0_clean = address_parts[0].strip(" \t\n\r\0\x0B-/#")
                street = address_parts[1] if p0_clean.isdigit() else address_parts[0]
            elif address_parts:
                street = address_parts[0]

        if street:
            street = re.sub(r'^[0-9\-\#]+\s+', '', street)
            route_name = f"Route via {street.strip()}"

    return route_name


def format_route_optimization(
    route: Any,
    stops_list: Optional[List[Any]] = None,
    orders_map: Optional[Dict[str, Any]] = None,
    center_obj: Optional[Any] = None,
    vehicle_obj: Optional[Any] = None,
) -> Dict[str, Any]:
    r_id = str(_get_val(route, 'id', _get_val(route, '_id', '')))

    # Load route stops if not provided
    if stops_list is None:
        if hasattr(route, 'stops'):
            stops_list = list(route.stops.select_related('order').all().order_by('stop_index'))
        else:
            from apps.routes.models import RouteStop
            stops_list = list(RouteStop.objects.filter(route_id=r_id).select_related('order').order_by('stop_index'))

    formatted_stops = []
    for stop in stops_list:
        seq = int(_get_val(stop, 'stop_index', _get_val(stop, 'sequence', 1)))
        order_obj = _get_val(stop, 'order')
        o_id = str(_get_val(stop, 'order_id', ''))
        if order_obj is None and orders_map and o_id in orders_map:
            order_obj = orders_map[o_id]

        eta = _get_val(stop, 'eta', _get_val(stop, 'estimated_arrival_time'))
        if hasattr(eta, 'isoformat'):
            eta_str = eta.isoformat()
        elif isinstance(eta, str):
            eta_str = eta
        else:
            eta_str = ''

        dist = float(_get_val(stop, 'distance_from_prev_km', _get_val(stop, 'distance_from_previous', 0.0)))
        stop_lat = float(_get_val(stop, 'latitude', _get_val(order_obj, 'latitude', 0.0) if order_obj else 0.0))
        stop_lng = float(_get_val(stop, 'longitude', _get_val(order_obj, 'longitude', 0.0) if order_obj else 0.0))
        addr = str(_get_val(stop, 'address', _get_val(order_obj, 'address', '') if order_obj else ''))

        formatted_stops.append({
            'sequence': seq,
            'order_id': o_id,
            'order': {'address': addr} if (addr or order_obj) else None,
            'latitude': stop_lat,
            'longitude': stop_lng,
            'priority': str(_get_val(order_obj, 'priority', 'normal')) if order_obj else 'normal',
            'eta': eta_str,
            'distance_from_previous': round(dist, 3),
        })

    formatted_stops.sort(key=lambda s: int(s.get('sequence', 0)))

    dc_id = _get_val(route, 'delivery_center_id')
    if center_obj is None:
        center_obj = _get_val(route, 'delivery_center')
        if center_obj is None and dc_id:
            from apps.centers.models import DeliveryCenter
            center_obj = DeliveryCenter.objects.filter(id=dc_id).first()

    v_id = _get_val(route, 'vehicle_id')
    if vehicle_obj is None:
        vehicle_obj = _get_val(route, 'vehicle')
        if vehicle_obj is None and v_id:
            from apps.vehicles.models import Vehicle
            vehicle_obj = Vehicle.objects.filter(id=v_id).first()

    route_name = compute_route_name(r_id, formatted_stops)

    departure_at = _get_val(route, 'departure_at')
    if hasattr(departure_at, 'isoformat'):
        departure_str = departure_at.isoformat()
    elif isinstance(departure_at, str):
        departure_str = departure_at
    else:
        departure_str = None

    status = _get_val(route, 'status', 'planned')
    profile = _get_val(route, 'profile', _get_val(route, 'optimization_profile', 'shortest_distance'))
    tot_dist = float(_get_val(route, 'total_distance_km', _get_val(route, 'total_distance', 0.0)))
    tot_time = int(float(_get_val(route, 'total_duration_min', _get_val(route, 'total_time', 0))))

    return {
        'route_id': r_id,
        'route_name': route_name,
        'delivery_center': {
            'id': str(_get_val(center_obj, 'id', '')),
            'name': str(_get_val(center_obj, 'name', '')),
            'latitude': float(_get_val(center_obj, 'latitude', 0.0)),
            'longitude': float(_get_val(center_obj, 'longitude', 0.0)),
        } if center_obj else None,
        'vehicle': {
            'id': str(_get_val(vehicle_obj, 'id', '')),
            'name': str(_get_val(vehicle_obj, 'name', '')),
        } if vehicle_obj else None,
        'total_distance': round(tot_dist, 3),
        'total_time': tot_time,
        'stops': formatted_stops,
        'comparison_batch_id': _get_val(route, 'comparison_batch_id'),
        'optimization_profile': str(profile),
        'status': str(status),
        'next_stop_sequence': 1 if formatted_stops else None,
        'departure_at': departure_str,
        'geometry': _get_val(route, 'geometry', []),
    }
