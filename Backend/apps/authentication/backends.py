import bcrypt
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class BcryptPasswordHasher(BasePasswordHasher):
    """
    Password hasher supporting both standard and legacy bcrypt hashes ($2y$, $2b$, $2a$),
    allowing seamless migration of user credentials without password resets.
    """
    algorithm = "bcrypt"
    iterations = 10

    def salt(self):
        return bcrypt.gensalt(rounds=self.iterations).decode('utf-8')

    def encode(self, password, salt):
        pw_bytes = password.encode('utf-8')
        salt_bytes = salt.encode('utf-8') if isinstance(salt, str) else salt
        hashed = bcrypt.hashpw(pw_bytes, salt_bytes).decode('utf-8')
        return f"{self.algorithm}${hashed}"

    def verify(self, password, encoded):
        if not encoded:
            return False

        if encoded.startswith(f"{self.algorithm}$"):
            raw_hash = encoded[len(self.algorithm) + 1:]
        else:
            raw_hash = encoded

        normalized = raw_hash
        if normalized.startswith('$2y$'):
            normalized = '$2b$' + normalized[4:]

        try:
            return bcrypt.checkpw(password.encode('utf-8'), normalized.encode('utf-8'))
        except Exception:
            return False

    def safe_summary(self, encoded):
        return {
            'algorithm': self.algorithm,
            'hash': mask_hash(encoded),
        }

    def must_update(self, encoded):
        # Always upgrade legacy bcrypt to Django's preferred hasher (PBKDF2) on successful login
        return True


class CaseInsensitiveEmailAuthBackend(ModelBackend):
    """
    Authenticates against settings.AUTH_USER_MODEL with case-insensitive email.
    """
    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        UserModel = get_user_model()
        target_email = email or username or kwargs.get('email')
        if not target_email or not password:
            return None

        try:
            user = UserModel.objects.get(email__iexact=str(target_email).strip())
        except UserModel.DoesNotExist:
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            user = UserModel.objects.filter(email__iexact=str(target_email).strip()).order_by('id').first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

