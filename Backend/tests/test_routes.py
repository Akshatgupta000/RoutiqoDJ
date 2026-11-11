import pytest
from rest_framework import status
from apps.routes.models import Route, RouteStop
from apps.orders.models import Order
from apps.vehicles.models import Vehicle
from apps.authentication.models import User


@pytest.mark.django_db
def test_route_generation_and_clear(auth_client, test_user):
    # 1. Create Center
    center = auth_client.post('/api/centers', {
        'name': 'Brooklyn Dispatch Hub',
        'latitude': 40.6782,
        'longitude': -73.9442,
    }, format='json').json()['data']

    # 2. Create Vehicle
    vehicle = auth_client.post('/api/vehicles', {
        'name': 'Delivery Van Alpha',
        'capacity': 50,
        'average_speed': 35.0,
        'delivery_center_id': center['id'],
    }, format='json').json()['data']

    # 3. Create Orders nearby
    for i in range(4):
        auth_client.post('/api/orders', {
            'address': f'{100 + i * 10} Atlantic Ave, Brooklyn',
            'latitude': 40.6800 + (i * 0.005),
            'longitude': -73.9400 - (i * 0.005),
            'delivery_date': '2026-05-10',
            'priority': 'priority' if i == 0 else 'normal',
        }, format='json')

    # 4. Generate Routes
    gen_res = auth_client.post('/api/routes/generate', {
        'delivery_center_id': center['id'],
        'date': '2026-05-10',
    }, format='json')
    assert gen_res.status_code == status.HTTP_201_CREATED
    comparisons = gen_res.json()['comparisons']
    assert len(comparisons) == 1

    route_data = comparisons[0]['shortest_distance_route']
    assert 'route_id' in route_data
    assert len(route_data['stops']) == 4

    # Priority order must be served first
    assert route_data['stops'][0]['priority'] == 'priority'

    # Check database persistence
    route_obj = Route.objects.get(id=route_data['route_id'])
    assert route_obj.status == Route.STATUS_PLANNED
    assert route_obj.stops.count() == 4

    # Vehicle load should be updated
    v_obj = Vehicle.objects.get(id=vehicle['id'])
    assert v_obj.current_load == 4

    # Fetch route by ID
    get_res = auth_client.get(f"/api/routes/{route_data['route_id']}")
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()['route_id'] == str(route_obj.id)

    # 5. Clear routes
    clear_res = auth_client.delete(f"/api/routes/clear?delivery_center_id={center['id']}")
    assert clear_res.status_code == status.HTTP_200_OK
    assert Route.objects.filter(delivery_center_id=center['id']).count() == 0

    # Orders should revert to pending and vehicle reset
    assert Order.objects.filter(delivery_center_id=center['id'], status=Order.STATUS_PENDING).count() == 4
    v_after = Vehicle.objects.get(id=vehicle['id'])
    assert v_after.current_load == 0


@pytest.mark.django_db
def test_bcrypt_legacy_password_compatibility(api_client):
    """
    Ensures existing users from MongoDB Atlas with $2y$ or $2b$ bcrypt passwords
    can authenticate seamlessly without password reset, and get upgraded to standard PBKDF2.
    """
    import bcrypt
    # Simulate a raw PHP/Laravel $2y$ hash stored in MongoDB Atlas for password 'secret123'
    raw_hash = bcrypt.hashpw(b'secret123', bcrypt.gensalt(10)).decode('utf-8')
    legacy_2y_hash = '$2y$' + raw_hash[4:]

    legacy_user = User.objects.create(
        email='legacy_user@example.com',
        name='Legacy User',
        password=legacy_2y_hash,
    )

    # Attempt login with original password
    login_res = api_client.post('/api/auth/login', {
        'email': 'legacy_user@example.com',
        'password': 'secret123',
    }, format='json')
    assert login_res.status_code == status.HTTP_200_OK
    data = login_res.json()
    assert data['success'] is True
    assert 'access_token' in data['data']

    # User password should now be safely upgraded to Django's standard hasher
    legacy_user.refresh_from_db()
    assert not legacy_user.password.startswith('$2y$')
    assert legacy_user.check_password('secret123')

