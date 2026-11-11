import pytest
from rest_framework import status
from core.database import db


def test_create_order_auto_assigns_to_nearest_center(auth_client):
    # Center in Brooklyn
    c = auth_client.post('/api/centers', {
        'name': 'Brooklyn Depot',
        'latitude': 40.6782,
        'longitude': -73.9442,
    }, format='json').json()['data']

    # Order ~1.5km from Brooklyn Depot
    payload = {
        'address': '123 Test St, Brooklyn',
        'latitude': 40.6850,
        'longitude': -73.9500,
        'priority': 'priority',
        'delivery_date': '2026-05-05',
    }
    response = auth_client.post('/api/orders', payload, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()['data']
    assert data['address'] == '123 Test St, Brooklyn'
    assert data['status'] == 'assigned'
    assert data['delivery_center_id'] == c['id']
    assert data['priority'] == 'priority'


def test_create_order_out_of_range_marks_pending(auth_client):
    # Center in Brooklyn
    auth_client.post('/api/centers', {
        'name': 'Brooklyn Depot',
        'latitude': 40.6782,
        'longitude': -73.9442,
    }, format='json')

    # Order in JFK Airport (> 20km away)
    payload = {
        'address': 'JFK Airport, Queens',
        'latitude': 40.6413,
        'longitude': -73.7781,
        'delivery_date': '2026-05-05',
    }
    response = auth_client.post('/api/orders', payload, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()['data']
    assert data['status'] == 'pending'
    assert data['delivery_center_id'] is None


def test_orders_pagination_and_filters(auth_client):
    c = auth_client.post('/api/centers', {
        'name': 'Hub 1',
        'latitude': 40.6782,
        'longitude': -73.9442,
    }, format='json').json()['data']

    for i in range(5):
        auth_client.post('/api/orders', {
            'address': f'Stop {i}',
            'latitude': 40.6780,
            'longitude': -73.9440,
            'delivery_date': '2026-05-05',
        }, format='json')

    res = auth_client.get('/api/orders?per_page=2&page=1')
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data['data']) == 2
    assert data['meta']['total'] == 5
    assert data['meta']['last_page'] == 3


def test_order_date_counts_and_bulk_counts(auth_client):
    for i in range(3):
        auth_client.post('/api/orders', {
            'address': f'Order {i}',
            'latitude': 40.6780,
            'longitude': -73.9440,
            'delivery_date': '2026-05-05',
        }, format='json')

    dc_res = auth_client.get('/api/orders/date-counts?year=2026&month=5')
    assert dc_res.status_code == status.HTTP_200_OK
    counts = dc_res.json()
    assert counts.get('2026-05-05') == 3

    bc_res = auth_client.get('/api/orders/bulk-counts?date=2026-05-05')
    assert bc_res.status_code == status.HTTP_200_OK
    bc = bc_res.json()
    assert bc['total'] == 3
    assert bc['pending'] == 3


def test_order_mark_all_delivered_and_clear_by_date(auth_client):
    for i in range(3):
        auth_client.post('/api/orders', {
            'address': f'Order {i}',
            'latitude': 40.6780,
            'longitude': -73.9440,
            'delivery_date': '2026-05-05',
        }, format='json')

    mark_res = auth_client.post('/api/orders/mark-all-delivered', {'date': '2026-05-05'}, format='json')
    assert mark_res.status_code == status.HTTP_200_OK
    assert mark_res.json()['updated_count'] == 3

    # Delete completed orders
    del_comp = auth_client.delete('/api/orders/completed?date=2026-05-05')
    assert del_comp.status_code == status.HTTP_200_OK
    assert del_comp.json()['deleted_count'] == 3
    assert db.orders.count_documents({}) == 0

