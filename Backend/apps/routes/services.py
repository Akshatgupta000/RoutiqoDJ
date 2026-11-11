import datetime
import math
import uuid
from typing import Any, Dict, List, Optional
import requests
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from core.helpers import DistanceHelper, RouteOptimizer, RouteTimingCalculator, get_priority_rank
from core.serializers import format_route_optimization
from apps.routes.models import Route, RouteStop
from apps.orders.models import Order
from apps.vehicles.models import Vehicle
from apps.centers.models import DeliveryCenter
from apps.orders.services import parse_date


SERVICE_SECONDS_PER_STOP = 180


def list_routes(user_id: Any) -> List[Dict[str, Any]]:
    routes = Route.objects.filter(user_id=user_id).select_related(
        'delivery_center', 'vehicle'
    ).prefetch_related('stops__order').order_by('-id')
    return [format_route_optimization(r) for r in routes]


def get_route_by_id(user_id: Any, route_id: Any) -> Optional[Dict[str, Any]]:
    try:
        route = Route.objects.filter(id=route_id, user_id=user_id).select_related(
            'delivery_center', 'vehicle'
        ).prefetch_related('stops__order').first()
        if not route:
            return None
        return format_route_optimization(route)
    except (ValueError, TypeError):
        return None


def fetch_geometry(center: Any, stops: List[Dict[str, Any]]) -> List[List[float]]:
    if not stops:
        return []

    center_lat = float(center.latitude if hasattr(center, 'latitude') else center['latitude'])
    center_lon = float(center.longitude if hasattr(center, 'longitude') else center['longitude'])

    coords_list = [f"{center_lon},{center_lat}"]
    for s in stops:
        s_lon = float(s.get('longitude', 0.0))
        s_lat = float(s.get('latitude', 0.0))
        coords_list.append(f"{s_lon},{s_lat}")
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
    vehicles: List[Vehicle],
    depot_lat: float,
    depot_lon: float,
) -> Dict[str, List[Dict[str, Any]]]:
    def order_sort_key(o: Dict[str, Any]):
        p_rank = get_priority_rank(o.get('priority'))
        lat = float(o.get('latitude', 0.0))
        lon = float(o.get('longitude', 0.0))
        angle = math.atan2(lat - depot_lat, lon - depot_lon)
        oid = str(o.get('id', ''))
        return (-p_rank, angle, oid)

    sorted_orders = sorted(orders, key=order_sort_key)
    sorted_vehicles = sorted(vehicles, key=lambda v: str(v.id))

    buckets: Dict[str, List[Dict[str, Any]]] = {}
    cursor = 0
    total_orders = len(sorted_orders)
    total_vehicles = len(sorted_vehicles)

    for index, vehicle in enumerate(sorted_vehicles):
        v_id_str = str(vehicle.id)
        remaining_orders = total_orders - cursor
        if remaining_orders <= 0:
            buckets[v_id_str] = []
            continue

        remaining_vehicles = total_vehicles - index
        fair_share = math.ceil(remaining_orders / remaining_vehicles)
        capacity = int(vehicle.capacity or 100)
        take = min(fair_share, capacity, remaining_orders)

        slice_orders = sorted_orders[cursor: cursor + take]
        cursor += len(slice_orders)
        buckets[v_id_str] = slice_orders

    return buckets


def clear_planned_routes_internal(user_id: Any, center_id: Any) -> None:
    planned_routes = Route.objects.filter(
        user_id=user_id,
        delivery_center_id=center_id,
        status=Route.STATUS_PLANNED
    )

    for route in planned_routes:
        stops = RouteStop.objects.filter(route=route).exclude(order__isnull=True)
        order_ids = [s.order_id for s in stops]
        if order_ids:
            Order.objects.filter(
                id__in=order_ids,
                user_id=user_id
            ).exclude(status=Order.STATUS_DELIVERED).update(
                vehicle=None,
                status=Order.STATUS_PENDING
            )

        if route.vehicle_id:
            Vehicle.objects.filter(id=route.vehicle_id).update(current_load=0)

        route.delete()


def capture_nearby_orders(user_id: Any, center: DeliveryCenter, radius_km: float = 10.0, date: Optional[str] = None) -> None:
    c_lat = float(center.latitude)
    c_lon = float(center.longitude)

    candidates = Order.objects.filter(
        user_id=user_id,
        status__in=[Order.STATUS_PENDING, Order.STATUS_ASSIGNED],
        delivery_center__isnull=True,
    )

    parsed_d = parse_date(date) if date else None

    for order in candidates:
        o_lat = float(order.latitude)
        o_lon = float(order.longitude)
        dist = DistanceHelper.km_between(o_lat, o_lon, c_lat, c_lon)

        if dist <= radius_km:
            if order.status == Order.STATUS_ASSIGNED:
                in_prog_stop = RouteStop.objects.filter(
                    order=order,
                    route__status=Route.STATUS_IN_PROGRESS
                ).exists()
                if in_prog_stop:
                    continue

            order.delivery_center = center
            order.status = Order.STATUS_PENDING
            order.vehicle = None
            if parsed_d:
                order.delivery_date = parsed_d
            order.save()


def persist_optimized_route(
    user_id: Any,
    center: DeliveryCenter,
    vehicle: Vehicle,
    ordered_stops: List[Dict[str, Any]],
    departure_at: datetime.datetime,
    profile: str,
    comparison_batch_id: str,
    geometry: Optional[List[List[float]]] = None,
) -> Dict[str, Any]:
    c_lat = float(center.latitude)
    c_lon = float(center.longitude)
    optimizer = RouteOptimizer(c_lat, c_lon)
    distance_km = optimizer.tour_distance_km(ordered_stops)

    v_speed = float(vehicle.average_speed or 25.0)
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

    route = Route.objects.create(
        user_id=user_id,
        delivery_center=center,
        vehicle=vehicle,
        comparison_batch_id=comparison_batch_id,
        profile=profile,
        total_distance_km=round(distance_km, 3),
        total_duration_min=round(float(timing['total_seconds']) / 60.0, 2),
        total_stops=len(ordered_stops),
        status=Route.STATUS_PLANNED,
        departure_at=departure_at,
        geometry=geometry,
    )

    stop_objects = []
    order_ids_to_assign = []
    for index, order_dict in enumerate(ordered_stops):
        leg_km = timing['leg_distances_km'][index] if index < len(timing['leg_distances_km']) else 0.0
        eta = timing['etas'][index] if index < len(timing['etas']) else None

        o_id = int(order_dict['id'])
        order_ids_to_assign.append(o_id)

        stop_objects.append(
            RouteStop(
                route=route,
                order_id=o_id,
                stop_index=index + 1,
                latitude=order_dict['latitude'],
                longitude=order_dict['longitude'],
                address=order_dict.get('address', ''),
                distance_from_prev_km=round(float(leg_km), 3),
                eta=eta,
            )
        )

    RouteStop.objects.bulk_create(stop_objects)

    if order_ids_to_assign:
        Order.objects.filter(id__in=order_ids_to_assign).update(
            status=Order.STATUS_ASSIGNED,
            vehicle=vehicle
        )

    vehicle.current_load = len(ordered_stops)
    vehicle.save(update_fields=['current_load'])

    return format_route_optimization(
        route=route,
        stops_list=stop_objects,
        center_obj=center,
        vehicle_obj=vehicle,
    )


def process_center(
    user_id: Any,
    center: DeliveryCenter,
    departure_at: datetime.datetime,
    date: str,
) -> List[Dict[str, Any]]:
    c_lat = float(center.latitude)
    c_lon = float(center.longitude)

    parsed_d = parse_date(date)
    if not parsed_d:
        return []

    orders_qs = Order.objects.filter(
        user_id=user_id,
        delivery_center=center,
        delivery_date=parsed_d,
        status__in=[Order.STATUS_PENDING, Order.STATUS_ASSIGNED]
    )

    # Exclude orders with in_progress routeStop
    in_progress_order_ids = RouteStop.objects.filter(
        route__status=Route.STATUS_IN_PROGRESS
    ).values_list('order_id', flat=True)

    if in_progress_order_ids:
        orders_qs = orders_qs.exclude(id__in=in_progress_order_ids)

    candidate_orders = list(orders_qs)
    filtered_orders = []
    for o in candidate_orders:
        dist = DistanceHelper.km_between(float(o.latitude), float(o.longitude), c_lat, c_lon)
        if dist <= 10.0:
            filtered_orders.append({
                'id': str(o.id),
                '_id': str(o.id),
                'latitude': float(o.latitude),
                'longitude': float(o.longitude),
                'address': o.address,
                'priority': o.priority,
            })

    if not filtered_orders:
        return []

    vehicles = list(Vehicle.objects.filter(
        user_id=user_id,
        is_available=True,
        delivery_center=center
    ).order_by('id'))

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

        vehicle = next((v for v in vehicles if str(v.id) == v_id_str), None)
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
            'delivery_center_id': str(center.id),
            'vehicle_id': v_id_str,
            'shortest_distance_route': route_formatted,
        })

    return comparisons


def generate_routes(
    user_id: Any,
    delivery_center_id: Optional[Any] = None,
    departure_at: Optional[datetime.datetime] = None,
    date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not date:
        raise ValidationError({'date': ['A delivery date is required to generate routes.']})

    if departure_at is None:
        departure_at = timezone.now()

    if delivery_center_id:
        center = DeliveryCenter.objects.filter(id=delivery_center_id, user_id=user_id).first()
        if not center:
            raise ValidationError({'delivery_center_id': ['The selected delivery center is invalid.']})
        centers = [center]
    else:
        centers = list(DeliveryCenter.objects.filter(user_id=user_id))

    comparisons = []
    for center in centers:
        clear_planned_routes_internal(user_id, center.id)
        capture_nearby_orders(user_id, center, 10.0, date)
        batch = process_center(user_id, center, departure_at, date)
        comparisons.extend(batch)

    return comparisons


def regenerate_routes_for_center(
    user_id: Any,
    delivery_center_id: Any,
    departure_at: Optional[datetime.datetime] = None,
    date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    center = DeliveryCenter.objects.filter(id=delivery_center_id, user_id=user_id).first()
    if not center:
        raise ValidationError({'center_id': ['The selected delivery center is invalid.']})

    clear_planned_routes_internal(user_id, center.id)
    capture_nearby_orders(user_id, center, 10.0, date)
    return generate_routes(user_id, str(center.id), departure_at, date)


def generate_route_for_vehicle(
    user_id: Any,
    vehicle_id: Any,
    departure_at: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    if departure_at is None:
        departure_at = timezone.now()

    vehicle = Vehicle.objects.filter(id=vehicle_id, user_id=user_id).select_related('delivery_center').first()
    if not vehicle:
        raise ValidationError({'vehicle_id': ['Vehicle not found.']})

    center = vehicle.delivery_center
    if not center:
        raise ValidationError({'vehicle_id': ['Vehicle does not belong to a valid delivery center.']})

    orders = list(Order.objects.filter(
        user_id=user_id,
        vehicle=vehicle,
        status=Order.STATUS_ASSIGNED
    ))

    if not orders:
        raise ValidationError({'vehicle_id': ['No assigned orders for this vehicle.']})

    c_lat = float(center.latitude)
    c_lon = float(center.longitude)

    order_dicts = [
        {
            'id': str(o.id),
            '_id': str(o.id),
            'latitude': float(o.latitude),
            'longitude': float(o.longitude),
            'address': o.address,
            'priority': o.priority,
        }
        for o in orders
    ]

    priority_orders = [o for o in order_dicts if o.get('priority') == 'priority']
    normal_orders = [o for o in order_dicts if o.get('priority') != 'priority']

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
        'delivery_center_id': str(center.id),
        'vehicle_id': str(vehicle.id),
        'route': route_formatted,
    }


def clear_routes(user_id: Any, delivery_center_id: Optional[Any] = None) -> None:
    qs = Route.objects.filter(user_id=user_id)
    if delivery_center_id:
        qs = qs.filter(delivery_center_id=delivery_center_id)

    routes = list(qs)
    for route in routes:
        stops = RouteStop.objects.filter(route=route).exclude(order__isnull=True)
        order_ids = [s.order_id for s in stops]

        if order_ids:
            Order.objects.filter(
                id__in=order_ids,
                user_id=user_id
            ).update(vehicle=None, status=Order.STATUS_PENDING)

        if route.vehicle_id:
            Vehicle.objects.filter(id=route.vehicle_id).update(current_load=0)

        route.delete()
