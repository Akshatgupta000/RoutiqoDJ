import datetime
import hashlib
import random
import re
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.authentication.models import User, PersonalAccessToken


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name = request.data.get('name')
        email = request.data.get('email')
        password = request.data.get('password')

        errors = {}
        if not name:
            errors['name'] = ['The name field is required.']
        if not email:
            errors['email'] = ['The email field is required.']
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", str(email)):
            errors['email'] = ['The email field must be a valid email address.']
        if not password:
            errors['password'] = ['The password field is required.']
        elif len(str(password)) < 8:
            errors['password'] = ['The password field must be at least 8 characters.']

        if errors:
            first_err = next(iter(errors.values()))[0]
            return Response({'success': False, 'message': first_err, 'errors': errors}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        email = email.strip().lower()

        # Check unique email
        if User.objects.filter(email=email).exists():
            return Response({
                'success': False,
                'message': 'Account already exists',
                'errors': {'email': ['Account already exists']}
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        user = User.objects.create_user(
            email=email,
            name=name.strip(),
            password=password
        )

        token, _ = user.create_token('auth_token')

        return Response({
            'success': True,
            'data': {
                'access_token': token,
                'token_type': 'Bearer',
                'user': user.to_dict(),
            },
            'message': 'Registration successful'
        }, status=status.HTTP_200_OK)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        errors = {}
        if not email:
            errors['email'] = ['The email field is required.']
        if not password:
            errors['password'] = ['The password field is required.']

        if errors:
            first_err = next(iter(errors.values()))[0]
            return Response({'success': False, 'message': first_err, 'errors': errors}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        email = email.strip().lower()
        user = User.objects.filter(email=email).first()

        if not user or not user.check_password(password):
            return Response({
                'success': False,
                'message': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)

        token, _ = user.create_token('auth_token')

        return Response({
            'success': True,
            'data': {
                'access_token': token,
                'token_type': 'Bearer',
                'user': user.to_dict(),
            },
            'message': 'Login successful'
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.auth and hasattr(request.auth, 'delete'):
            request.auth.delete()

        return Response({
            'success': True,
            'message': 'Logged out successfully'
        }, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'success': True,
            'data': request.user.to_dict()
        }, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'message': 'The email field is required.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        email = email.strip().lower()
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({
                'success': False,
                'message': 'No account found with this email address.'
            }, status=status.HTTP_404_NOT_FOUND)

        otp = str(random.randint(0, 999999)).zfill(6)
        hashed_otp = hashlib.sha256(otp.encode('utf-8')).hexdigest()
        expires = timezone.now() + datetime.timedelta(minutes=15)

        user.reset_otp_hash = hashed_otp
        user.reset_otp_expires = expires
        user.save(update_fields=['reset_otp_hash', 'reset_otp_expires', 'updated_at'])

        try:
            send_mail(
                subject='Routiqo Password Reset Code',
                message=f'Your verification code is: {otp}. It expires in 15 minutes.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception:
            pass

        return Response({
            'success': True,
            'message': 'A verification code has been sent to your email.'
        }, status=status.HTTP_200_OK)


class VerifyOtpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')

        if not email or not otp:
            return Response({'message': 'Email and OTP are required.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if len(str(otp)) != 6:
            return Response({'message': 'OTP must be 6 digits.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        email = email.strip().lower()
        hashed_otp = hashlib.sha256(str(otp).encode('utf-8')).hexdigest()

        user = User.objects.filter(
            email=email,
            reset_otp_hash=hashed_otp,
            reset_otp_expires__gt=timezone.now()
        ).first()

        if not user:
            return Response({
                'success': False,
                'message': 'Invalid or expired verification code.'
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': 'Code verified successfully.'
        }, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        password = request.data.get('password')
        password_confirmation = request.data.get('password_confirmation')

        if not email or not otp or not password:
            return Response({'message': 'Email, OTP and password are required.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if password != password_confirmation:
            return Response({'message': 'Password confirmation does not match.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if len(str(password)) < 8:
            return Response({'message': 'Password must be at least 8 characters.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        email = email.strip().lower()
        hashed_otp = hashlib.sha256(str(otp).encode('utf-8')).hexdigest()

        user = User.objects.filter(
            email=email,
            reset_otp_hash=hashed_otp,
            reset_otp_expires__gt=timezone.now()
        ).first()

        if not user:
            return Response({
                'success': False,
                'message': 'Verification failed. Code may be expired.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update password and clear OTP
        user.set_password(password)
        user.reset_otp_hash = None
        user.reset_otp_expires = None
        user.save()

        # Revoke all tokens
        user.tokens.all().delete()

        return Response({
            'success': True,
            'message': 'Your password has been reset successfully.'
        }, status=status.HTTP_200_OK)
