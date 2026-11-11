import re
from typing import Any, Dict, List, Optional
from core.database import db, id_query, serialize_doc


def format_delivery_center(center: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not center:
        return None
    c_id = str(center.get('id', center.get('_id', '')))
    return {
        'id': c_id,
        'name': str(center.get('name', '')),
        'latitude': float(center.get('latitude', 0.0)),
        'longitude': float(center.get('longitude', 0.0)),
    }


def format_vehicle(vehicle: Optional[Dict[str, Any]], load_center: bool = False) -> Optional[Dict[str, Any]]:
    if not vehicle:
        return None
    v_id = str(vehicle.get('id', vehicle.get('_id', '')))
    dc_id = vehicle.get('delivery_center_id')
    dc_id_str = str(dc_id) if dc_id is not None else None

    res = {
        'id': v_id,
        'name': str(vehicle.get('name', '')),
        'vehicle_number': vehicle.get('vehicle_number'),
        'capacity': int(vehicle.get('capacity', 0)),
        'current_load': int(vehicle.get('current_load', 0)),
        'is_available': bool(vehicle.get('is_available', True)),
        'average_speed': float(vehicle.get('average_speed', 25.0)),
        'delivery_center_id': dc_id_str,
    }

    if load_center:
        center_doc = None
        if dc_id:
            center_doc = db.delivery_centers.find_one(id_query(dc_id))
        res['delivery_center'] = format_delivery_center(center_doc)

    return res


def format_order(order: Optional[Dict[str, Any]], load_relations: bool = True) -> Optional[Dict[str, Any]]:
    if not order:
        return None
    o_id = str(order.get('id', order.get('_id', '')))
    dc_id = order.get('delivery_center_id')
    v_id = order.get('vehicle_id')
    
    delivery_date = order.get('delivery_date')
    if hasattr(delivery_date, 'strftime'):
        date_str = delivery_date.strftime('%Y-%m-%d')
    elif isinstance(delivery_date, str):
        date_str = delivery_date[:10]
    else:
        date_str = None

    status = order.get('status', 'pending')
    if hasattr(status, 'value'):
        status = status.value

    priority = order.get('priority', 'normal')
    if hasattr(priority, 'value'):
        priority = priority.value

    res = {
        'id': o_id,
        'address': str(order.get('address', '')),
        'latitude': float(order.get('latitude', 0.0)),
        'longitude': float(order.get('longitude', 0.0)),
        'delivery_date': date_str,
        'delivery_center_id': str(dc_id) if dc_id is not None else None,
        'vehicle_id': str(v_id) if v_id is not None else None,
        'status': str(status),
        'priority': str(priority),
    }

    if load_relations:
        center_doc = db.delivery_centers.find_one(id_query(dc_id)) if dc_id else None
        res['delivery_center'] = format_delivery_center(center_doc)
        
        vehicle_doc = db.vehicles.find_one(id_query(v_id)) if v_id else None
        res['vehicle'] = format_vehicle(vehicle_doc) if vehicle_doc else None

    return res


def compute_route_name(route_id: str, stops: List[Dict[str, Any]]) -> str:
    route_name = f"Route #{route_id[-6:]}"
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
    route: Dict[str, Any],
    stops_docs: Optional[List[Dict[str, Any]]] = None,
    orders_map: Optional[Dict[str, Dict[str, Any]]] = None,
    center_doc: Optional[Dict[str, Any]] = None,
    vehicle_doc: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    r_id = str(route.get('id', route.get('_id', '')))

    # Load route stops if not provided
    if stops_docs is None:
        stops_docs = list(db.route_stops.find({'route_id': r_id}).sort('sequence', 1))

    stops_docs.sort(key=lambda s: int(s.get('sequence', 0)))

    # Gather missing order details
    if orders_map is None:
        orders_map = {}
        missing_order_ids = [
            s.get('order_id') for s in stops_docs
            if s.get('order_id') and str(s.get('order_id')) not in orders_map
        ]
        if missing_order_ids:
            from core.database import to_object_id
            found_orders = db.orders.find({
                '$or': [
                    {'_id': {'$in': [to_object_id(oid) for oid in missing_order_ids]}},
                    {'_id': {'$in': [str(oid) for oid in missing_order_ids]}},
                ]
            })
            for o in found_orders:
                orders_map[str(o['_id'])] = o

    formatted_stops = []
    for stop in stops_docs:
        order_id = str(stop.get('order_id', ''))
        order = orders_map.get(order_id)
        
        eta = stop.get('estimated_arrival_time')
        if hasattr(eta, 'isoformat'):
            eta_str = eta.isoformat()
        elif isinstance(eta, str):
            eta_str = eta
        else:
            eta_str = ''

        formatted_stops.append({
            'sequence': int(stop.get('sequence', 1)),
            'order_id': order_id,
            'order': {'address': order.get('address')} if order else None,
            'latitude': float(order.get('latitude', 0.0)) if order else 0.0,
            'longitude': float(order.get('longitude', 0.0)) if order else 0.0,
            'priority': str(order.get('priority', 'normal')) if order else 'normal',
            'eta': eta_str,
            'distance_from_previous': round(float(stop.get('distance_from_previous', 0.0)), 3),
        })

    # Load center and vehicle if needed
    dc_id = route.get('delivery_center_id')
    if center_doc is None and dc_id:
        center_doc = db.delivery_centers.find_one(id_query(dc_id))

    v_id = route.get('vehicle_id')
    if vehicle_doc is None and v_id:
        vehicle_doc = db.vehicles.find_one(id_query(v_id))

    route_name = compute_route_name(r_id, formatted_stops)

    departure_at = route.get('departure_at')
    if hasattr(departure_at, 'isoformat'):
        departure_str = departure_at.isoformat()
    elif isinstance(departure_at, str):
        departure_str = departure_at
    else:
        departure_str = None

    status = route.get('status', 'planned')
    if hasattr(status, 'value'):
        status = status.value

    profile = route.get('optimization_profile', 'shortest_distance')
    if hasattr(profile, 'value'):
        profile = profile.value

    return {
        'route_id': r_id,
        'route_name': route_name,
        'delivery_center': {
            'id': str(center_doc.get('_id', center_doc.get('id', ''))),
            'name': str(center_doc.get('name', '')),
            'latitude': float(center_doc.get('latitude', 0.0)),
            'longitude': float(center_doc.get('longitude', 0.0)),
        } if center_doc else None,
        'vehicle': {
            'id': str(vehicle_doc.get('_id', vehicle_doc.get('id', ''))),
            'name': str(vehicle_doc.get('name', '')),
        } if vehicle_doc else None,
        'total_distance': round(float(route.get('total_distance', 0.0)), 3),
        'total_time': int(route.get('total_time', 0)),
        'stops': formatted_stops,
        'comparison_batch_id': route.get('comparison_batch_id'),
        'optimization_profile': str(profile),
        'status': str(status),
        'next_stop_sequence': route.get('next_stop_sequence'),
        'departure_at': departure_str,
        'geometry': route.get('geometry', []),
    }
