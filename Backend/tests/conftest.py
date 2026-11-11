import pytest
import mongomock
from rest_framework.test import APIClient
from core.database import set_db, now_utc
from core.authentication import hash_password, MongoUser


@pytest.fixture(autouse=True)
def mock_mongo():
    client = mongomock.MongoClient()
    test_db = client['logiroute_test']
    set_db(test_db)
    yield test_db
    # Clean up
    set_db(None)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(mock_mongo):
    user_doc = {
        'name': 'Test Dispatcher',
        'email': 'dispatcher@example.com',
        'password': hash_password('password123'),
        'created_at': now_utc(),
        'updated_at': now_utc(),
    }
    res = mock_mongo.users.insert_one(user_doc)
    user_doc['_id'] = res.inserted_id

    user = MongoUser(user_doc)
    token, _ = user.create_token('auth_token')
    return {
        'user': user,
        'doc': user_doc,
        'id': str(user_doc['_id']),
        'token': token,
    }


@pytest.fixture
def auth_client(test_user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {test_user['token']}")
    return client

