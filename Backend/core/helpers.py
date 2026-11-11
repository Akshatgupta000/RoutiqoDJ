import datetime
import math
import random
import re
from typing import Any, Dict, List, Optional, Tuple, Callable
import requests
from django.conf import settings
from rest_framework.exceptions import ValidationError


class DistanceHelper:
    EARTH_RADIUS_KM = 6371.0

    @staticmethod
    def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2.0) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2.0) ** 2)

        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
        return DistanceHelper.EARTH_RADIUS_KM * c

    @staticmethod
    def between_points(from_pt: Dict[str, float], to_pt: Dict[str, float]) -> float:
        return DistanceHelper.km_between(from_pt['lat'], from_pt['lon'], to_pt['lat'], to_pt['lon'])


def distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return DistanceHelper.km_between(lat1, lon1, lat2, lon2)


def get_priority_rank(priority: Any) -> int:
    p = str(priority).lower() if priority else 'normal'
    if p in ('priority', 'high', 'urgent'):
        return 2
    return 1


class RouteTimingCalculator:
    def compute(
        self,
        departure: datetime.datetime,
        ordered_stops: List[Dict[str, Any]],
        depot_lat: float,
        depot_lon: float,
        average_speed_kmh: float,
        service_seconds_per_stop: int = 180,
    ) -> Dict[str, Any]:
        if not ordered_stops:
            return {'total_seconds': 0, 'etas': [], 'leg_distances_km': []}

        speed = max(average_speed_kmh, 1.0)
        etas: List[datetime.datetime] = []
        legs: List[float] = []
        cursor = departure
        prev = {'lat': depot_lat, 'lon': depot_lon}
        total = 0

        for stop in ordered_stops:
            point = {'lat': float(stop['latitude']), 'lon': float(stop['longitude'])}
            km = DistanceHelper.between_points(prev, point)
            legs.append(round(km, 3))
            travel = int(round((km / speed) * 3600))
            total += travel
            cursor = cursor + datetime.timedelta(seconds=travel)
            etas.append(cursor)
            cursor = cursor + datetime.timedelta(seconds=service_seconds_per_stop)
            total += service_seconds_per_stop
            prev = point

        return_km = DistanceHelper.between_points(prev, {'lat': depot_lat, 'lon': depot_lon})
        return_travel = int(round((return_km / speed) * 3600))
        total += return_travel

        return {
            'total_seconds': total,
            'etas': etas,
            'leg_distances_km': legs,
        }


class RouteOptimizer:
    TWO_OPT_EPSILON = 1e-6

    def __init__(self, depot_lat: float, depot_lon: float):
        self.depot_lat = float(depot_lat)
        self.depot_lon = float(depot_lon)

    def depot_point(self) -> Dict[str, float]:
        return {'lat': self.depot_lat, 'lon': self.depot_lon}

    def order_point(self, order: Dict[str, Any]) -> Dict[str, float]:
        return {'lat': float(order['latitude']), 'lon': float(order['longitude'])}

    def build_shortest_distance_tour(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not orders:
            return []

        tour = self.nearest_neighbor_by_distance(orders)
        return self.two_opt_by_metric(
            tour,
            lambda a, b: DistanceHelper.between_points(a, b),
            0,
            orders
        )

    def tour_distance_km(self, ordered_stops: List[Dict[str, Any]]) -> float:
        return self.closed_tour_length(ordered_stops, lambda a, b: DistanceHelper.between_points(a, b))

    def nearest_neighbor_by_distance(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unvisited = {str(o.get('id', o.get('_id'))): o for o in orders}
        tour: List[Dict[str, Any]] = []
        current = self.depot_point()

        while unvisited:
            best_id = self.select_next_by_distance(unvisited, current)
            best = unvisited.pop(best_id)
            tour.append(best)
            current = self.order_point(best)

        return tour

    def select_next_by_distance(self, unvisited: Dict[str, Dict[str, Any]], current: Dict[str, float]) -> str:
        candidates = list(unvisited.values())

        def sort_key(o: Dict[str, Any]):
            dist = DistanceHelper.between_points(current, self.order_point(o))
            priority_rank = get_priority_rank(o.get('priority'))
            # Discretize distance with TWO_OPT_EPSILON to handle tie-breaks
            # Higher priority rank comes first on tie
            return (round(dist / self.TWO_OPT_EPSILON), -priority_rank)

        candidates.sort(key=sort_key)
        best = candidates[0]
        return str(best.get('id', best.get('_id')))

    def two_opt_by_metric(
        self,
        tour: List[Dict[str, Any]],
        edge_metric: Callable[[Dict[str, float], Dict[str, float]], float],
        service_per_stop: int,
        all_orders: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        n = len(tour)
        if n < 4:
            return self.ensure_unique_order_coverage(tour, all_orders)

        best = list(tour)
        best_cost = self.closed_tour_length(best, edge_metric) + n * service_per_stop
        improved = True

        while improved:
            improved = False
            for i in range(0, n - 1):
                for j in range(i + 2, n):
                    candidate = self.reverse_segment(best, i + 1, j)
                    cost = self.closed_tour_length(candidate, edge_metric) + len(candidate) * service_per_stop
                    if cost + self.TWO_OPT_EPSILON < best_cost:
                        best = candidate
                        best_cost = cost
                        improved = True

        return self.ensure_unique_order_coverage(best, all_orders)

    def closed_tour_length(
        self,
        tour: List[Dict[str, Any]],
        edge_metric: Callable[[Dict[str, float], Dict[str, float]], float]
    ) -> float:
        if not tour:
            return 0.0

        prev = self.depot_point()
        total = 0.0

        for stop in tour:
            p = self.order_point(stop)
            total += edge_metric(prev, p)
            prev = p

        total += edge_metric(prev, self.depot_point())
        return total

    def reverse_segment(self, tour: List[Dict[str, Any]], i: int, j: int) -> List[Dict[str, Any]]:
        prefix = tour[:i]
        middle = tour[i:j + 1]
        suffix = tour[j + 1:]
        return prefix + list(reversed(middle)) + suffix

    def ensure_unique_order_coverage(
        self,
        tour: List[Dict[str, Any]],
        source: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        seen = set()
        deduped = []

        for order in tour:
            oid = str(order.get('id', order.get('_id')))
            if oid not in seen:
                seen.add(oid)
                deduped.append(order)

        if len(deduped) != len(source):
            missing = [
                o for o in source
                if str(o.get('id', o.get('_id'))) not in seen
            ]
            missing.sort(key=lambda o: -get_priority_rank(o.get('priority')))
            deduped.extend(missing)

        return deduped


def is_point_in_polygon(lat: float, lng: float, polygon: List[List[float]]) -> bool:
    """
    Ray Casting Algorithm for Point-in-Polygon check.
    polygon is a list of [lat, lng] coordinate pairs.
    Matches exact algorithm in ServiceZoneService.php.
    """
    inside = False
    n = len(polygon)
    if n < 3:
        return False

    j = n - 1
    for i in range(n):
        xi = float(polygon[i][0])
        yi = float(polygon[i][1])
        xj = float(polygon[j][0])
        yj = float(polygon[j][1])

        intersect = ((yi > lng) != (yj > lng)) and (lat < (xj - xi) * (lng - yi) / (yj - yi) + xi)
        if intersect:
            inside = not inside
        j = i

    return inside


class VehicleHelper:
    @staticmethod
    def generate_indian_vehicle_number(prefix: str = 'DL01') -> str:
        series = chr(random.randint(65, 90)) + chr(random.randint(65, 90))
        number = str(random.randint(0, 9999)).zfill(4)
        return f"{prefix}{series}{number}"

    @staticmethod
    def get_rto_prefix_from_center_name(name: str) -> str:
        n = name.lower()
        # Uttar Pradesh
        if 'lucknow' in n or 'charbagh' in n or 'indira nagar' in n:
            return 'UP32'
        if 'noida' in n:
            return 'UP16'
        if 'ghaziabad' in n:
            return 'UP14'
        if 'kanpur' in n:
            return 'UP78'
        # Delhi
        if 'delhi' in n:
            return 'DL01'
        # Maharashtra
        if 'mumbai' in n or 'andheri' in n:
            return 'MH01'
        if 'pune' in n:
            return 'MH12'
        # Karnataka
        if 'bangalore' in n or 'bengaluru' in n or 'koramangala' in n:
            return 'KA01'
        # West Bengal
        if 'kolkata' in n or 'howrah' in n:
            return 'WB01'
        # Tamil Nadu
        if 'chennai' in n:
            return 'TN01'
        # Haryana
        if 'gurgaon' in n or 'gurugram' in n:
            return 'HR26'
        # Default
        return 'DL01'


def geocode_address(query: str) -> Dict[str, Any]:
    """
    Geocode an address using Nominatim OpenStreetMap API.
    """
    url = 'https://nominatim.openstreetmap.org/search'
    headers = {
        'User-Agent': f"{settings.APP_NAME} ({settings.APP_URL})",
    }
    params = {
        'q': query,
        'format': 'json',
        'limit': 1,
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code in (429, 403):
            raise Exception('Geocoding service rate limited or blocked. Please try again later or use coordinates.')
        if resp.status_code != 200:
            raise Exception(f'Nominatim Geocoding service unavailable (Status: {resp.status_code})')

        data = resp.json()
        if not isinstance(data, list) or not data:
            raise ValidationError({
                'address': 'The provided address could not be located. Please try a more specific address or city name.'
            })

        result = data[0]
        return {
            'lat': float(result['lat']),
            'lng': float(result['lon']),
            'display_name': result.get('display_name', ''),
        }
    except Exception as e:
        if isinstance(e, ValidationError):
            raise e
        raise ValidationError({
            'address': f"Geocoding failed: {str(e)}"
        })
