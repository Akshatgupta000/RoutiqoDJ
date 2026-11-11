import datetime
import hashlib
import secrets
from typing import Any, Dict, Tuple
import bcrypt
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email: str, name: str = '', password: str = None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email).strip().lower()
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, name=name.strip(), **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, name: str = '', password: str = None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(unique=True, db_index=True)
    reset_otp_hash = models.CharField(max_length=64, null=True, blank=True)
    reset_otp_expires = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table = 'authentication_user'
        ordering = ['-id']

    def __str__(self) -> str:
        return f"{self.email} ({self.id})"

    def check_password(self, raw_password: str) -> bool:
        """
        Supports Django default hashers, BcryptPasswordHasher (prefixed with bcrypt$),
        and raw legacy bcrypt hashes ($2y$, $2b$, $2a$).
        Transparently re-hashes legacy passwords to default hasher upon successful verification.
        """
        if not self.password or not raw_password:
            return False

        if self.password.startswith(('$2y$', '$2b$', '$2a$')):
            normalized = self.password
            if normalized.startswith('$2y$'):
                normalized = '$2b$' + normalized[4:]
            try:
                matched = bcrypt.checkpw(raw_password.encode('utf-8'), normalized.encode('utf-8'))
                if matched:
                    # Transparently upgrade to Django's standard PBKDF2 hasher
                    self.set_password(raw_password)
                    self.save(update_fields=['password'])
                return matched
            except Exception:
                return False

        return super().check_password(raw_password)

    def to_dict(self) -> Dict[str, Any]:
        """Preserves exact API serialization contract for user data."""
        return {
            'id': str(self.id),
            '_id': str(self.id),
            'name': self.name,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def create_token(self, name: str = 'auth_token') -> Tuple[str, str]:
        """
        Creates a Sanctum-compatible personal access token: "<token_id>|<plain_token>".
        Returns (full_token, token_id_str).
        """
        plain_part = secrets.token_urlsafe(30)[:40]
        hashed = hashlib.sha256(plain_part.encode('utf-8')).hexdigest()

        token_obj = PersonalAccessToken.objects.create(
            user=self,
            name=name,
            token=hashed,
            abilities=['*'],
        )
        token_id_str = str(token_obj.id)
        full_token = f"{token_id_str}|{plain_part}"
        return full_token, token_id_str


class PersonalAccessToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tokens')
    name = models.CharField(max_length=255, default='auth_token')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    abilities = models.JSONField(default=list)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'authentication_personalaccesstoken'
        ordering = ['-id']

    def __str__(self) -> str:
        return f"Token({self.id}, user={self.user_id}, name={self.name})"

