import pytest
from rest_framework import status
from apps.vehicles.models import Vehicle
from apps.orders.models import Order


@pytest.mark.django_db
def test_can_create_and_fetch_centers(auth_client):
    payload = {
        'name': 'Brooklyn Main Hub',
        'latitude': 40.6782,
        'longitude': -73.9442,
    }
    response = auth_client.post('/api/centers', payload, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()['data']
    assert data['name'] == 'Brooklyn Main Hub'
    assert data['latitude'] == 40.6782
    assert data['longitude'] == -73.9442
    assert 'id' in data

    # Fetch all centers
    get_res = auth_client.get('/api/centers')
    assert get_res.status_code == status.HTTP_200_OK
    centers = get_res.json()['data']
    assert len(centers) == 1
    assert centers[0]['name'] == 'Brooklyn Main Hub'


@pytest.mark.django_db
def test_center_validation_fails_for_invalid_coordinates(auth_client):
    payload = {
        'name': 'Invalid Hub',
        'latitude': 100.0,  # Invalid latitude (> 90)
        'longitude': -73.9442,
    }
    response = auth_client.post('/api/centers', payload, format='json')
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert 'latitude' in response.json()['errors']


@pytest.mark.django_db
def test_update_center(auth_client):
    c_res = auth_client.post('/api/centers', {'name': 'Hub Old', 'latitude': 40.0, 'longitude': -74.0}, format='json')
    c_id = c_res.json()['data']['id']

    patch_res = auth_client.patch(f'/api/centers/{c_id}', {'name': 'Hub New'}, format='json')
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()['data']['name'] == 'Hub New'


@pytest.mark.django_db
def test_delete_center_cleans_up_and_reassigns_orders(auth_client, test_user):
    # Create two hubs
    c1 = auth_client.post('/api/centers', {'name': 'Hub 1', 'latitude': 40.7000, 'longitude': -74.0000}, format='json').json()['data']
    c2 = auth_client.post('/api/centers', {'name': 'Hub 2', 'latitude': 40.7100, 'longitude': -74.0050}, format='json').json()['data']

    # Create vehicle for hub 1
    v = auth_client.post('/api/vehicles', {
        'name': 'Van 1',
        'capacity': 10,
        'delivery_center_id': c1['id']
    }, format='json').json()['data']

    # Create order near hub 1
    order = auth_client.post('/api/orders', {
        'address': 'Near Hub 1',
        'latitude': 40.7010,
        'longitude': -74.0010,
        'delivery_date': '2026-05-05',
    }, format='json').json()['data']
    assert order['delivery_center_id'] == c1['id']

    # Delete Hub 1
    del_res = auth_client.delete(f'/api/centers/{c1["id"]}')
    assert del_res.status_code == status.HTTP_200_OK
    del_data = del_res.json()
    assert 'message' in del_data
    assert len(del_data['centers']) == 1  # Hub 2 remains

    # Vehicle of Hub 1 should be deleted
    assert Vehicle.objects.filter(delivery_center_id=c1['id']).count() == 0

    # Order should be reassigned to Hub 2 (within 10km)
    order_obj = Order.objects.get(id=order['id'])
    assert str(order_obj.delivery_center_id) == str(c2['id'])
