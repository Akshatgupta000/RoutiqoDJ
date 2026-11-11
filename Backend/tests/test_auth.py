import hashlib
import pytest
from rest_framework import status
from apps.authentication.models import User


def test_root_health(api_client):
    response = api_client.get('/')
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'status': 'Routiqo Backend Running'}


def test_up_health(api_client):
    response = api_client.get('/up')
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'status': 'ok'}

    api_up = api_client.get('/api/up')
    assert api_up.status_code == status.HTTP_200_OK
    assert api_up.json() == {'status': 'ok'}


@pytest.mark.django_db
def test_register_success(api_client):
    payload = {
        'name': 'Alice Dispatch',
        'email': 'alice@example.com',
        'password': 'password123',
    }
    response = api_client.post('/api/auth/register', payload, format='json')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data['success'] is True
    assert 'access_token' in data['data']
    assert data['data']['user']['email'] == 'alice@example.com'


@pytest.mark.django_db
def test_register_duplicate_email(api_client, test_user):
    payload = {
        'name': 'Duplicate User',
        'email': 'dispatcher@example.com',
        'password': 'password123',
    }
    response = api_client.post('/api/auth/register', payload, format='json')
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert data['success'] is False
    assert 'already exists' in data['message']


@pytest.mark.django_db
def test_register_validation_fails(api_client):
    response = api_client.post('/api/auth/register', {'name': 'No Email'}, format='json')
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()['success'] is False


@pytest.mark.django_db
def test_login_success(api_client, test_user):
    payload = {
        'email': 'dispatcher@example.com',
        'password': 'password123',
    }
    response = api_client.post('/api/auth/login', payload, format='json')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data['success'] is True
    assert 'access_token' in data['data']


@pytest.mark.django_db
def test_login_invalid_password(api_client, test_user):
    payload = {
        'email': 'dispatcher@example.com',
        'password': 'wrongpassword',
    }
    response = api_client.post('/api/auth/login', payload, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()['success'] is False


@pytest.mark.django_db
def test_me_authenticated(auth_client, test_user):
    response = auth_client.get('/api/user')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data['success'] is True
    assert data['data']['email'] == 'dispatcher@example.com'


@pytest.mark.django_db
def test_me_unauthenticated(api_client):
    response = api_client.get('/api/user')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_logout(auth_client):
    response = auth_client.post('/api/logout')
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['success'] is True


@pytest.mark.django_db
def test_forgot_and_verify_and_reset_password(api_client, test_user):
    # Forgot password
    fp_res = api_client.post('/api/auth/forgot-password', {'email': 'dispatcher@example.com'}, format='json')
    assert fp_res.status_code == status.HTTP_200_OK
    assert fp_res.json()['success'] is True

    # Retrieve stored user
    user = User.objects.get(email='dispatcher@example.com')
    assert user.reset_otp_hash is not None

    # Let's set a known OTP hash for testing
    otp = '123456'
    hashed = hashlib.sha256(otp.encode('utf-8')).hexdigest()
    user.reset_otp_hash = hashed
    user.save(update_fields=['reset_otp_hash'])

    # Verify OTP
    v_res = api_client.post('/api/auth/verify-otp', {'email': 'dispatcher@example.com', 'otp': '123456'}, format='json')
    assert v_res.status_code == status.HTTP_200_OK
    assert v_res.json()['success'] is True

    # Reset password
    rp_res = api_client.post('/api/auth/reset-password', {
        'email': 'dispatcher@example.com',
        'otp': '123456',
        'password': 'newpassword123',
        'password_confirmation': 'newpassword123',
    }, format='json')
    assert rp_res.status_code == status.HTTP_200_OK
    assert rp_res.json()['success'] is True

    # Login with new password
    login_res = api_client.post('/api/auth/login', {
        'email': 'dispatcher@example.com',
        'password': 'newpassword123',
    }, format='json')
    assert login_res.status_code == status.HTTP_200_OK
