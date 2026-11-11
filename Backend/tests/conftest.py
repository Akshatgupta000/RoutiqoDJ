import pytest
from rest_framework.test import APIClient
from apps.authentication.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    user = User.objects.create_user(
        name='Test Dispatcher',
        email='dispatcher@example.com',
        password='password123',
    )
    token, _ = user.create_token('auth_token')
    return {
        'user': user,
        'id': str(user.id),
        'token': token,
    }


@pytest.fixture
def auth_client(test_user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {test_user['token']}")
    return client
