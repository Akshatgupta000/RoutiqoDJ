import pytest
from rest_framework import status
from apps.vehicles.models import Vehicle


@pytest.mark.django_db
def test_create_vehicle_with_auto_generated_number(auth_client):
    c = auth_client.post('/api/centers', {
        'name': 'Lucknow Depot',
        'latitude': 26.8467,
        'longitude': 80.9462,
    }, format='json').json()['data']

    payload = {
        'name': 'Electric Van 1',
        'capacity': 25,
        'average_speed': 30.0,
        'delivery_center_id': c['id'],
    }
    response = auth_client.post('/api/vehicles', payload, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()['data']
    assert data['name'] == 'Electric Van 1'
    assert data['capacity'] == 25
    assert data['average_speed'] == 30.0
    assert data['is_available'] is True
    # RTO prefix for Lucknow is UP32
    assert data['vehicle_number'].startswith('UP32')


@pytest.mark.django_db
def test_vehicle_validation_invalid_capacity(auth_client):
    c = auth_client.post('/api/centers', {
        'name': 'Central Depot',
        'latitude': 28.6139,
        'longitude': 77.2090,
    }, format='json').json()['data']

    response = auth_client.post('/api/vehicles', {
        'name': 'Bad Capacity Van',
        'capacity': 0,
        'delivery_center_id': c['id'],
    }, format='json')
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert 'capacity' in response.json()['errors']


@pytest.mark.django_db
def test_list_and_update_vehicle(auth_client):
    c = auth_client.post('/api/centers', {
        'name': 'Noida Depot',
        'latitude': 28.5355,
        'longitude': 77.3910,
    }, format='json').json()['data']

    v = auth_client.post('/api/vehicles', {
        'name': 'Van A',
        'capacity': 15,
        'delivery_center_id': c['id'],
    }, format='json').json()['data']

    # List vehicles
    list_res = auth_client.get('/api/vehicles')
    assert list_res.status_code == status.HTTP_200_OK
    assert len(list_res.json()['data']) == 1

    # Update vehicle
    patch_res = auth_client.patch(f"/api/vehicles/{v['id']}", {'capacity': 20}, format='json')
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()['data']['capacity'] == 20


@pytest.mark.django_db
def test_reset_fleet(auth_client):
    c = auth_client.post('/api/centers', {
        'name': 'Delhi Hub',
        'latitude': 28.7041,
        'longitude': 77.1025,
    }, format='json').json()['data']

    v = auth_client.post('/api/vehicles', {
        'name': 'Van Delhi',
        'capacity': 15,
        'delivery_center_id': c['id'],
    }, format='json').json()['data']

    # Manually set vehicle unavailable and load
    v_obj = Vehicle.objects.get(id=v['id'])
    v_obj.is_available = False
    v_obj.current_load = 10
    v_obj.save()

    reset_res = auth_client.post('/api/vehicles/reset-fleet', {'delivery_center_id': c['id']}, format='json')
    assert reset_res.status_code == status.HTTP_200_OK
    assert reset_res.json()['message'] == 'Fleet and active routes reset successful'

    v_after = Vehicle.objects.get(id=v['id'])
    assert v_after.is_available is True
    assert v_after.current_load == 0


@pytest.mark.django_db
def test_delete_vehicle(auth_client):
    c = auth_client.post('/api/centers', {
        'name': 'Hub X',
        'latitude': 28.0,
        'longitude': 77.0,
    }, format='json').json()['data']

    v = auth_client.post('/api/vehicles', {
        'name': 'Van to delete',
        'capacity': 10,
        'delivery_center_id': c['id'],
    }, format='json').json()['data']

    del_res = auth_client.delete(f"/api/vehicles/{v['id']}")
    assert del_res.status_code == status.HTTP_204_NO_CONTENT
    assert Vehicle.objects.filter(id=v['id']).count() == 0
