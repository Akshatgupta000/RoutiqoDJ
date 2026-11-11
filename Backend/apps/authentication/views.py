import datetime
import hashlib
import random
import re
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError

from core.database import db, now_utc, id_query
from core.authentication import MongoUser, hash_password, check_password


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
        existing = db.users.find_one({'email': email})
        if existing:
            return Response({
                'success': False,
                'message': 'Account already exists',
                'errors': {'email': ['Account already exists']}
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        user_doc = {
            'name': name.strip(),
            'email': email,
            'password': hash_password(password),
            'reset_password_otp': None,
            'reset_password_expires': None,
            'created_at': now_utc(),
            'updated_at': now_utc(),
        }
        res = db.users.insert_one(user_doc)
        user_doc['_id'] = res.inserted_id

        user = MongoUser(user_doc)
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
        user_doc = db.users.find_one({'email': email})

        if not user_doc or not check_password(password, user_doc.get('password', '')):
            return Response({
                'success': False,
                'message': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)

        user = MongoUser(user_doc)
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
        if request.auth and '_id' in request.auth:
            db.personal_access_tokens.delete_one({'_id': request.auth['_id']})

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
        user_doc = db.users.find_one({'email': email})
        if not user_doc:
            return Response({
                'success': False,
                'message': 'No account found with this email address.'
            }, status=status.HTTP_404_NOT_FOUND)

        otp = str(random.randint(0, 999999)).zfill(6)
        hashed_otp = hashlib.sha256(otp.encode('utf-8')).hexdigest()
        expires = now_utc() + datetime.timedelta(minutes=15)

        db.users.update_one(
            {'_id': user_doc['_id']},
            {
                '$set': {
                    'reset_password_otp': hashed_otp,
                    'reset_password_expires': expires,
                    'updated_at': now_utc(),
                }
            }
        )

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

        user_doc = db.users.find_one({
            'email': email,
            'reset_password_otp': hashed_otp,
            'reset_password_expires': {'$gt': now_utc()}
        })

        if not user_doc:
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

        user_doc = db.users.find_one({
            'email': email,
            'reset_password_otp': hashed_otp,
            'reset_password_expires': {'$gt': now_utc()}
        })

        if not user_doc:
            return Response({
                'success': False,
                'message': 'Verification failed. Code may be expired.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update password and clear OTP
        db.users.update_one(
            {'_id': user_doc['_id']},
            {
                '$set': {
                    'password': hash_password(password),
                    'reset_password_otp': None,
                    'reset_password_expires': None,
                    'updated_at': now_utc(),
                }
            }
        )

        # Revoke all tokens
        db.personal_access_tokens.delete_many({'tokenable_id': str(user_doc['_id'])})

        return Response({
            'success': True,
            'message': 'Your password has been reset successfully.'
        }, status=status.HTTP_200_OK)
