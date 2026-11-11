import datetime
import pytest
from core.helpers import (
    DistanceHelper,
    RouteOptimizer,
    RouteTimingCalculator,
    distance,
    get_priority_rank,
    is_point_in_polygon,
)


def test_haversine_helper():
    # Distance between Brooklyn (40.6782, -73.9442) and Queens (40.7282, -73.7949)
    km = distance(40.6782, -73.9442, 40.7282, -73.7949)
    assert km > 10.0
    assert km < 20.0


def test_nearest_neighbor_produces_valid_sequence():
    optimizer = RouteOptimizer(0.0, 0.0)  # Depot at origin

    order1 = {'id': '1', 'latitude': 1.0, 'longitude': 0.0, 'priority': 'normal'}
    order2 = {'id': '2', 'latitude': 3.0, 'longitude': 0.0, 'priority': 'normal'}
    order3 = {'id': '3', 'latitude': 10.0, 'longitude': 0.0, 'priority': 'normal'}

    # Unordered list
    orders = [order3, order1, order2]

    tour = optimizer.build_shortest_distance_tour(orders)

    assert len(tour) == 3
    # Starts from depot (0,0) -> order1 (1,0) -> order2 (3,0) -> order3 (10,0)
    assert tour[0]['id'] == '1'
    assert tour[1]['id'] == '2'
    assert tour[2]['id'] == '3'


def test_total_distance_is_positive_and_logical():
    optimizer = RouteOptimizer(0.0, 0.0)
    order1 = {'id': '1', 'latitude': 1.0, 'longitude': 0.0, 'priority': 'normal'}
    order2 = {'id': '2', 'latitude': 3.0, 'longitude': 0.0, 'priority': 'normal'}

    orders = [order1, order2]
    tour = optimizer.build_shortest_distance_tour(orders)

    dist = optimizer.tour_distance_km(tour)
    assert dist > 0.0
    assert dist > 600.0  # (0,0) -> (1,0) -> (3,0) -> (0,0)


def test_timing_calculator():
    calc = RouteTimingCalculator()
    departure = datetime.datetime(2026, 5, 5, 8, 0, 0, tzinfo=datetime.timezone.utc)
    stops = [
        {'id': '1', 'latitude': 0.1, 'longitude': 0.0},
        {'id': '2', 'latitude': 0.2, 'longitude': 0.0},
    ]
    res = calc.compute(
        departure=departure,
        ordered_stops=stops,
        depot_lat=0.0,
        depot_lon=0.0,
        average_speed_kmh=30.0,
        service_seconds_per_stop=180,
    )
    assert res['total_seconds'] > 0
    assert len(res['etas']) == 2
    assert len(res['leg_distances_km']) == 2
    assert res['etas'][0] > departure
    assert res['etas'][1] > res['etas'][0]


def test_ray_casting_algorithm():
    polygon = [
        [0.0, 0.0],
        [4.0, 0.0],
        [4.0, 4.0],
        [0.0, 4.0],
    ]
    # Point inside (2.0, 2.0)
    assert is_point_in_polygon(2.0, 2.0, polygon) is True
    # Point outside (5.0, 5.0)
    assert is_point_in_polygon(5.0, 5.0, polygon) is False

