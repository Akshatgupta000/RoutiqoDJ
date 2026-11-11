import datetime
import math
import uuid
from typing import Any, Dict, List, Optional
import requests
from django.conf import settings
from rest_framework.exceptions import NotFound, ValidationError

from core.database import db, now_utc, id_query, to_object_id
from core.helpers import DistanceHelper, RouteOptimizer, RouteTimingCalculator, get_priority_rank
from core.serializers import format_route_optimization


SERVICE_SECONDS_PER_STOP = 180


def list_routes(user_id: str) -> List[Dict[str, Any]]:
    docs = list(db.routes.find({'user_id': str(user_id)}).sort('_id', -1))
    return [format_route_optimization(r) for r in docs]


def get_route_by_id(user_id: str, route_id: str) -> Optional[Dict[str, Any]]:
    q = id_query(route_id)
    q['user_id'] = str(user_id)
    route = db.routes.find_one(q)
    if not route:
        return None
    return format_route_optimization(route)


def fetch_geometry(center: Dict[str, Any], stops: List[Dict[str, Any]]) -> List[List[float]]:
    if not stops:
        return []

    center_lat = float(center['latitude'])
    center_lon = float(center['longitude'])

    coords_list = [f"{center_lon},{center_lat}"]
    for s in stops:
        coords_list.append(f"{float(s['longitude'])},{float(s['latitude'])}")
    coords_list.append(f"{center_lon},{center_lat}")

    points_str = ';'.join(coords_list)
    osrm_url = f"{settings.OSRM_ENDPOINT}/route/v1/driving/{points_str}"

    try:
        resp = requests.get(
            osrm_url,
            params={'overview': 'full', 'geometries': 'geojson'},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 'Ok' and data.get('routes'):
                coords = data['routes'][0].get('geometry', {}).get('coordinates', [])
                if coords:
                    # Convert [lng, lat] to [lat, lng] for Leaflet
                    return [[p[1], p[0]] for p in coords]
    except Exception:
        pass

    return []


def cluster_orders_by_vehicle_capacity(
    orders: List[Dict[str, Any]],
    vehicles: List[Dict[str, Any]],
    depot_lat: float,
    depot_lon: float,
) -> Dict[str, List[Dict[str, Any]]]:
    # Match Laravel sort:
    # 1. priority rank desc
    # 2. angle atan2(lat - depot_lat, lon - depot_lon) asc
    # 3. id asc
    def order_sort_key(o: Dict[str, Any]):
        p_rank = get_priority_rank(o.get('priority'))
        lat = float(o.get('latitude', 0.0))
        lon = float(o.get('longitude', 0.0))
        angle = math.atan2(lat - depot_lat, lon - depot_lon)
        oid = str(o.get('id', o.get('_id', '')))
        return (-p_rank, angle, oid)

    sorted_orders = sorted(orders, key=order_sort_key)
    sorted_vehicles = sorted(vehicles, key=lambda v: str(v.get('id', v.get('_id', ''))))

    buckets: Dict[str, List[Dict[str, Any]]] = {}
    cursor = 0
    total_orders = len(sorted_orders)
    total_vehicles = len(sorted_vehicles)

    for index, vehicle in enumerate(sorted_vehicles):
        v_id_str = str(vehicle['_id'])
        remaining_orders = total_orders - cursor
        if remaining_orders <= 0:
            buckets[v_id_str] = []
            continue

        remaining_vehicles = total_vehicles - index
        fair_share = math.ceil(remaining_orders / remaining_vehicles)
        capacity = int(vehicle.get('capacity', 100))
        take = min(fair_share, capacity, remaining_orders)

        slice_orders = sorted_orders[cursor : cursor + take]
        cursor += len(slice_orders)
        buckets[v_id_str] = slice_orders

    return buckets


def clear_planned_routes_internal(user_id: str, center_id: Any) -> None:
    c_str = str(center_id)
    planned_routes = list(db.routes.find({
        'user_id': str(user_id),
        'status': 'planned',
        '$or': [{'delivery_center_id': c_str}, {'delivery_center_id': to_object_id(c_str)}]
    }))

    for route in planned_routes:
        r_id = str(route['_id'])
        stops = list(db.route_stops.find({'route_id': r_id}))
        order_ids = [s.get('order_id') for s in stops if s.get('order_id')]

        if order_ids:
            # Unassign from vehicle and revert to pending if not delivered
            db.orders.update_many(
                {
                    'user_id': str(user_id),
                    'status': {'$ne': 'delivered'},
                    '$or': [
                        {'_id': {'$in': [to_object_id(oid) for oid in order_ids]}},
                        {'_id': {'$in': [str(oid) for oid in order_ids]}},
                    ]
                },
                {'$set': {'vehicle_id': None, 'status': 'pending', 'updated_at': now_utc()}}
            )

        v_id = route.get('vehicle_id')
        if v_id:
            db.vehicles.update_one(id_query(v_id), {'$set': {'current_load': 0, 'updated_at': now_utc()}})

        db.route_stops.delete_many({'route_id': r_id})
        db.routes.delete_one({'_id': route['_id']})


def capture_nearby_orders(user_id: str, center: Dict[str, Any], radius_km: float = 10.0, date: Optional[str] = None) -> None:
    center_id_str = str(center['_id'])
    c_lat = float(center['latitude'])
    c_lon = float(center['longitude'])

    # Find pending/assigned orders without delivery_center_id (including orphans)
    candidates = list(db.orders.find({
        'user_id': str(user_id),
        'status': {'$in': ['pending', 'assigned']},
        'delivery_center_id': None,
    }))

    for order in candidates:
        o_lat = float(order.get('latitude', 0.0))
        o_lon = float(order.get('longitude', 0.0))
        dist = DistanceHelper.km_between(o_lat, o_lon, c_lat, c_lon)

        if dist <= radius_km:
            # Don't capture if in an in-progress route
            if order.get('status') == 'assigned':
                in_prog_stop = db.route_stops.find_one({'order_id': str(order['_id'])})
                if in_prog_stop:
                    in_prog_route = db.routes.find_one({'_id': to_object_id(in_prog_stop.get('route_id')), 'status': 'in_progress'})
                    if in_prog_route:
                        continue

            updates: Dict[str, Any] = {
                'delivery_center_id': center_id_str,
                'status': 'pending',
                'vehicle_id': None,
                'updated_at': now_utc(),
            }
            if date:
                updates['delivery_date'] = date[:10]

            db.orders.update_one({'_id': order['_id']}, {'$set': updates})


def persist_optimized_route(
    user_id: str,
    center: Dict[str, Any],
    vehicle: Dict[str, Any],
    ordered_stops: List[Dict[str, Any]],
    departure_at: datetime.datetime,
    profile: str,
    comparison_batch_id: str,
    geometry: Optional[List[List[float]]] = None,
) -> Dict[str, Any]:
    c_lat = float(center['latitude'])
    c_lon = float(center['longitude'])
    optimizer = RouteOptimizer(c_lat, c_lon)
    distance_km = optimizer.tour_distance_km(ordered_stops)

    v_speed = float(vehicle.get('average_speed', 25.0))
    timing = RouteTimingCalculator().compute(
        departure=departure_at,
        ordered_stops=ordered_stops,
        depot_lat=c_lat,
        depot_lon=c_lon,
        average_speed_kmh=v_speed,
        service_seconds_per_stop=SERVICE_SECONDS_PER_STOP,
    )

    if geometry is None:
        geometry = fetch_geometry(center, ordered_stops)

    route_doc = {
        'user_id': str(user_id),
        'delivery_center_id': str(center['_id']),
        'vehicle_id': str(vehicle['_id']),
        'comparison_batch_id': comparison_batch_id,
        'optimization_profile': profile,
        'total_distance': round(distance_km, 3),
        'total_time': int(timing['total_seconds']),
        'status': 'planned',
        'next_stop_sequence': None,
        'departure_at': departure_at,
        'geometry': geometry,
        'created_at': now_utc(),
        'updated_at': now_utc(),
    }
    r_res = db.routes.insert_one(route_doc)
    route_doc['_id'] = r_res.inserted_id
    r_id_str = str(route_doc['_id'])

    stops_docs = []
    for index, order in enumerate(ordered_stops):
        leg_km = timing['leg_distances_km'][index] if index < len(timing['leg_distances_km']) else 0.0
        eta = timing['etas'][index] if index < len(timing['etas']) else None

        stop_doc = {
            'route_id': r_id_str,
            'order_id': str(order['_id']),
            'sequence': index + 1,
            'distance_from_previous': round(float(leg_km), 3),
            'estimated_arrival_time': eta,
            'created_at': now_utc(),
            'updated_at': now_utc(),
        }
        db.route_stops.insert_one(stop_doc)
        stops_docs.append(stop_doc)

        db.orders.update_one(
            {'_id': order['_id']},
            {
                '$set': {
                    'status': 'assigned',
                    'vehicle_id': str(vehicle['_id']),
                    'updated_at': now_utc(),
                }
            }
        )

    # Update vehicle load
    db.vehicles.update_one(
        {'_id': vehicle['_id']},
        {'$set': {'current_load': len(ordered_stops), 'updated_at': now_utc()}}
    )

    orders_map = {str(o['_id']): o for o in ordered_stops}
    return format_route_optimization(
        route=route_doc,
        stops_docs=stops_docs,
        orders_map=orders_map,
        center_doc=center,
        vehicle_doc=vehicle,
    )


def process_center(
    user_id: str,
    center: Dict[str, Any],
    departure_at: datetime.datetime,
    date: str,
) -> List[Dict[str, Any]]:
    c_id_str = str(center['_id'])
    c_lat = float(center['latitude'])
    c_lon = float(center['longitude'])

    # Find pending/assigned orders for center on date that are not in in_progress routes
    dt_str = date[:10]
    try:
        dt = datetime.datetime.strptime(dt_str, '%Y-%m-%d')
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        date_q = {
            '$or': [
                {'delivery_date': {'$gte': start, '$lte': end}},
                {'delivery_date': {'$regex': f"^{dt_str}"}},
                {'delivery_date': dt_str},
            ]
        }
    except Exception:
        date_q = {'delivery_date': dt_str}

    orders_query = {
        'user_id': str(user_id),
        '$or': [{'delivery_center_id': c_id_str}, {'delivery_center_id': to_object_id(c_id_str)}],
        'status': {'$in': ['pending', 'assigned']},
    }
    orders_query.update(date_q)

    all_orders = list(db.orders.find(orders_query))

    # Exclude orders with in_progress routeStop
    filtered_orders = []
    for o in all_orders:
        stop = db.route_stops.find_one({'order_id': str(o['_id'])})
        if stop:
            r = db.routes.find_one({'_id': to_object_id(stop.get('route_id')), 'status': 'in_progress'})
            if r:
                continue

        dist = DistanceHelper.km_between(float(o.get('latitude', 0.0)), float(o.get('longitude', 0.0)), c_lat, c_lon)
        if dist <= 10.0:
            filtered_orders.append(o)

    if not filtered_orders:
        return []

    # Get available vehicles
    vehicles = list(db.vehicles.find({
        'user_id': str(user_id),
        'is_available': True,
        '$or': [{'delivery_center_id': c_id_str}, {'delivery_center_id': to_object_id(c_id_str)}],
    }).sort('_id', 1))

    if not vehicles:
        raise ValidationError({'delivery_center_id': ['No available vehicles exist for this delivery center.']})

    clusters = cluster_orders_by_vehicle_capacity(
        orders=filtered_orders,
        vehicles=vehicles,
        depot_lat=c_lat,
        depot_lon=c_lon,
    )

    pending_routes = {}
    for v_id_str, bucket in clusters.items():
        if not bucket:
            continue

        vehicle = next((v for v in vehicles if str(v['_id']) == v_id_str), None)
        if not vehicle:
            continue

        batch_id = str(uuid.uuid4())

        priority_orders = [o for o in bucket if o.get('priority') == 'priority']
        normal_orders = [o for o in bucket if o.get('priority') != 'priority']

        optimizer = RouteOptimizer(c_lat, c_lon)
        priority_tour = optimizer.build_shortest_distance_tour(priority_orders)
        normal_tour = optimizer.build_shortest_distance_tour(normal_orders)
        final_tour = priority_tour + normal_tour

        pending_routes[v_id_str] = {
            'vehicle': vehicle,
            'tour': final_tour,
            'batch_id': batch_id,
        }

    if not pending_routes:
        return []

    comparisons = []
    for v_id_str, data in pending_routes.items():
        vehicle = data['vehicle']
        tour = data['tour']
        batch_id = data['batch_id']

        route_formatted = persist_optimized_route(
            user_id=user_id,
            center=center,
            vehicle=vehicle,
            ordered_stops=tour,
            departure_at=departure_at,
            profile='shortest_distance',
            comparison_batch_id=batch_id,
        )

        comparisons.append({
            'comparison_batch_id': batch_id,
            'delivery_center_id': c_id_str,
            'vehicle_id': v_id_str,
            'shortest_distance_route': route_formatted,
        })

    return comparisons


def generate_routes(
    user_id: str,
    delivery_center_id: Optional[str] = None,
    departure_at: Optional[datetime.datetime] = None,
    date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not date:
        raise ValidationError({'date': ['A delivery date is required to generate routes.']})

    if departure_at is None:
        departure_at = now_utc()

    if delivery_center_id:
        c_q = id_query(delivery_center_id)
        c_q['user_id'] = str(user_id)
        center = db.delivery_centers.find_one(c_q)
        if not center:
            raise ValidationError({'delivery_center_id': ['The selected delivery center is invalid.']})
        centers = [center]
    else:
        centers = list(db.delivery_centers.find({'user_id': str(user_id)}))

    comparisons = []
    for center in centers:
        clear_planned_routes_internal(user_id, center['_id'])
        capture_nearby_orders(user_id, center, 10.0, date)
        batch = process_center(user_id, center, departure_at, date)
        comparisons.extend(batch)

    return comparisons


def regenerate_routes_for_center(
    user_id: str,
    delivery_center_id: str,
    departure_at: Optional[datetime.datetime] = None,
    date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    c_q = id_query(delivery_center_id)
    c_q['user_id'] = str(user_id)
    center = db.delivery_centers.find_one(c_q)
    if not center:
        raise ValidationError({'center_id': ['The selected delivery center is invalid.']})

    clear_planned_routes_internal(user_id, center['_id'])
    capture_nearby_orders(user_id, center, 10.0, date)
    return generate_routes(user_id, str(center['_id']), departure_at, date)


def generate_route_for_vehicle(
    user_id: str,
    vehicle_id: str,
    departure_at: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    if departure_at is None:
        departure_at = now_utc()

    v_q = id_query(vehicle_id)
    v_q['user_id'] = str(user_id)
    vehicle = db.vehicles.find_one(v_q)
    if not vehicle:
        raise ValidationError({'vehicle_id': ['Vehicle not found.']})

    dc_id = vehicle.get('delivery_center_id')
    center = db.delivery_centers.find_one(id_query(dc_id)) if dc_id else None
    if not center:
        raise ValidationError({'vehicle_id': ['Vehicle does not belong to a valid delivery center.']})

    v_id_str = str(vehicle['_id'])
    orders = list(db.orders.find({
        'user_id': str(user_id),
        'vehicle_id': v_id_str,
        'status': 'assigned',
    }))

    if not orders:
        raise ValidationError({'vehicle_id': ['No assigned orders for this vehicle.']})

    c_lat = float(center['latitude'])
    c_lon = float(center['longitude'])

    priority_orders = [o for o in orders if o.get('priority') == 'priority']
    normal_orders = [o for o in orders if o.get('priority') != 'priority']

    optimizer = RouteOptimizer(c_lat, c_lon)
    priority_tour = optimizer.build_shortest_distance_tour(priority_orders)
    normal_tour = optimizer.build_shortest_distance_tour(normal_orders)
    final_tour = priority_tour + normal_tour

    batch_id = str(uuid.uuid4())
    route_formatted = persist_optimized_route(
        user_id=user_id,
        center=center,
        vehicle=vehicle,
        ordered_stops=final_tour,
        departure_at=departure_at,
        profile='shortest_distance',
        comparison_batch_id=batch_id,
    )

    return {
        'comparison_batch_id': batch_id,
        'delivery_center_id': str(center['_id']),
        'vehicle_id': v_id_str,
        'route': route_formatted,
    }


def clear_routes(user_id: str, delivery_center_id: Optional[str] = None) -> None:
    q: Dict[str, Any] = {'user_id': str(user_id)}
    if delivery_center_id:
        dc_str = str(delivery_center_id)
        q['$or'] = [{'delivery_center_id': dc_str}, {'delivery_center_id': to_object_id(dc_str)}]

    routes = list(db.routes.find(q))
    for route in routes:
        r_id = str(route['_id'])
        stops = list(db.route_stops.find({'route_id': r_id}))
        order_ids = [s.get('order_id') for s in stops if s.get('order_id')]

        if order_ids:
            # Revert orders back to pending
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

        v_id = route.get('vehicle_id')
        if v_id:
            db.vehicles.update_one(id_query(v_id), {'$set': {'current_load': 0, 'updated_at': now_utc()}})

        db.route_stops.delete_many({'route_id': r_id})
        db.routes.delete_one({'_id': route['_id']})

