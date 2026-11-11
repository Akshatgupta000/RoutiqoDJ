import hashlib
from typing import Optional, Tuple
from django.utils import timezone
from rest_framework import authentication, exceptions
from apps.authentication.models import User, PersonalAccessToken


class BearerTokenAuthentication(authentication.BaseAuthentication):
    """
    Sanctum-compatible Bearer Token Authentication for DRF with Django ORM.
    Supports token format: "<token_id>|<plain_text_token>" or raw "<plain_text_token>".
    """
    keyword = 'Bearer'

    def authenticate(self, request) -> Optional[Tuple[User, PersonalAccessToken]]:
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

    def authenticate_credentials(self, token: str) -> Tuple[User, PersonalAccessToken]:
        token_obj = None

        if '|' in token:
            token_id_str, plain_token = token.split('|', 1)
            hashed_token = hashlib.sha256(plain_token.encode('utf-8')).hexdigest()
            try:
                token_obj = PersonalAccessToken.objects.filter(
                    id=token_id_str,
                    token=hashed_token
                ).select_related('user').first()
            except (ValueError, TypeError):
                token_obj = None
        else:
            hashed_token = hashlib.sha256(token.encode('utf-8')).hexdigest()
            token_obj = PersonalAccessToken.objects.filter(
                token=hashed_token
            ).select_related('user').first()

        if not token_obj:
            raise exceptions.AuthenticationFailed('Unauthenticated.')

        if token_obj.expires_at and token_obj.expires_at < timezone.now():
            raise exceptions.AuthenticationFailed('Token has expired.')

        # Update last_used_at timestamp
        PersonalAccessToken.objects.filter(id=token_obj.id).update(last_used_at=timezone.now())

        user = token_obj.user
        if not user or not user.is_active:
            raise exceptions.AuthenticationFailed('User not found.')

        return user, token_obj
