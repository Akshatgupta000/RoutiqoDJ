import pytest
from rest_framework import status


@pytest.mark.django_db
def test_service_zones_generate_and_check(auth_client):
    c = auth_client.post('/api/centers', {
        'name': 'Center 1',
        'latitude': 40.7000,
        'longitude': -74.0000,
    }, format='json').json()['data']

    # Square polygon around (40.70, -74.00)
    polygon = [
        [40.6900, -74.0100],
        [40.7100, -74.0100],
        [40.7100, -73.9900],
        [40.6900, -73.9900],
    ]

    zones_payload = {
        'zones': [
            {
                'hub_id': c['id'],
                'polygon': polygon,
            }
        ]
    }
    gen_res = auth_client.post('/api/zones/generate', zones_payload, format='json')
    assert gen_res.status_code == status.HTTP_200_OK
    assert gen_res.json()['message'] == 'Service zones updated successfully'

    # List zones
    list_res = auth_client.get('/api/zones')
    assert list_res.status_code == status.HTTP_200_OK
    zones = list_res.json()
    assert len(zones) == 1
    assert str(zones[0]['delivery_center_id']) == str(c['id'])
    assert zones[0]['delivery_center']['name'] == 'Center 1'

    # Check point inside polygon
    check_inside = auth_client.get('/api/zones/check?lat=40.7000&lng=-74.0000')
    assert check_inside.status_code == status.HTTP_200_OK
    assert str(check_inside.json()['hub_id']) == str(c['id'])

    # Check point outside polygon
    check_outside = auth_client.get('/api/zones/check?lat=40.8000&lng=-74.1000')
    assert check_outside.status_code == status.HTTP_404_NOT_FOUND
