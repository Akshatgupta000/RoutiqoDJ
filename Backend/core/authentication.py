import hashlib
import secrets
from typing import Any, Dict, Optional, Tuple
import bcrypt
from bson import ObjectId
from django.utils import timezone
from rest_framework import authentication, exceptions
from core.database import db, to_object_id, now_utc, id_query


def hash_password(password: str) -> str:
    """Hash password using bcrypt compatible with PHP Hash::make."""
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def check_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash (supports $2y$, $2b$, $2a$)."""
    if not password or not hashed:
        return False
    # PHP's $2y$ is identical to standard bcrypt $2b$/$2a$
    normalized_hash = hashed
    if normalized_hash.startswith('$2y$'):
        normalized_hash = '$2b$' + normalized_hash[4:]
    try:
        return bcrypt.checkpw(password.encode('utf-8'), normalized_hash.encode('utf-8'))
    except Exception:
        return False


class MongoUser:
    def __init__(self, doc: Dict[str, Any]):
        self.doc = doc
        self._id = str(doc.get('_id', ''))
        self.id = self._id
        self.pk = self._id
        self.name = doc.get('name', '')
        self.email = doc.get('email', '')
        self.is_authenticated = True
        self.is_anonymous = False
        self.is_active = True

    def __str__(self) -> str:
        return f"{self.email} ({self.id})"

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.doc)
        d['id'] = self.id
        d['_id'] = self.id
        d.pop('password', None)
        d.pop('remember_token', None)
        d.pop('reset_password_otp', None)
        for k, v in d.items():
            if isinstance(v, ObjectId):
                d[k] = str(v)
            elif hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
        return d

    def create_token(self, name: str = 'auth_token') -> Tuple[str, str]:
        """
        Creates a new Sanctum-compatible personal access token.
        Returns (plain_text_token, token_id).
        Format: "<token_id>|<random_40_chars>"
        """
        plain_part = secrets.token_urlsafe(30)[:40]
        hashed = hashlib.sha256(plain_part.encode('utf-8')).hexdigest()
        
        token_doc = {
            'name': name,
            'token': hashed,
            'abilities': ['*'],
            'tokenable_id': str(self.id),
            'tokenable_type': 'App\\Models\\User',
            'last_used_at': None,
            'expires_at': None,
            'created_at': now_utc(),
            'updated_at': now_utc(),
        }
        res = db.personal_access_tokens.insert_one(token_doc)
        token_id = str(res.inserted_id)
        full_token = f"{token_id}|{plain_part}"
        return full_token, token_id


class BearerTokenAuthentication(authentication.BaseAuthentication):
    """
    Sanctum-compatible Bearer Token Authentication for DRF.
    Supports token format: "<token_id>|<plain_text_token>" or raw "<plain_text_token>".
    """
    keyword = 'Bearer'

    def authenticate(self, request) -> Optional[Tuple[MongoUser, Dict[str, Any]]]:
        auth_header = authentication.get_authorization_header(request).split()

        if not auth_header:
            return None

        if auth_header[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth_header) == 1:
            raise exceptions.AuthenticationFailed('Invalid token header. No credentials provided.')
        elif len(auth_header) > 2:
            raise exceptions.AuthenticationFailed('Invalid token header. Token string should not contain spaces.')

        try:
            token = auth_header[1].decode('utf-8')
        except UnicodeError:
            raise exceptions.AuthenticationFailed('Invalid token header. Token string contains invalid characters.')

        return self.authenticate_credentials(token)

    def authenticate_credentials(self, token: str) -> Tuple[MongoUser, Dict[str, Any]]:
        token_doc = None

        if '|' in token:
            token_id, plain_token = token.split('|', 1)
            hashed_token = hashlib.sha256(plain_token.encode('utf-8')).hexdigest()
            query = id_query(token_id)
            query['token'] = hashed_token
            token_doc = db.personal_access_tokens.find_one(query)
        else:
            hashed_token = hashlib.sha256(token.encode('utf-8')).hexdigest()
            token_doc = db.personal_access_tokens.find_one({'token': hashed_token})

        if not token_doc:
            raise exceptions.AuthenticationFailed('Unauthenticated.')

        expires_at = token_doc.get('expires_at')
        if expires_at and expires_at < now_utc():
            raise exceptions.AuthenticationFailed('Token has expired.')

        # Update last_used_at
        db.personal_access_tokens.update_one(
            {'_id': token_doc['_id']},
            {'$set': {'last_used_at': now_utc()}}
        )

        user_id = token_doc.get('tokenable_id')
        user_doc = db.users.find_one(id_query(user_id))

        if not user_doc:
            raise exceptions.AuthenticationFailed('User not found.')

        user = MongoUser(user_doc)
        return user, token_doc
