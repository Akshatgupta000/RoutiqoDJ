from django.urls import path
from apps.authentication.views import (
    RegisterView,
    LoginView,
    LogoutView,
    MeView,
    ForgotPasswordView,
    VerifyOtpView,
    ResetPasswordView,
)

urlpatterns = [
    path('auth/register', RegisterView.as_view(), name='auth-register'),
    path('auth/login', LoginView.as_view(), name='auth-login'),
    path('auth/forgot-password', ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('auth/verify-otp', VerifyOtpView.as_view(), name='auth-verify-otp'),
    path('auth/reset-password', ResetPasswordView.as_view(), name='auth-reset-password'),
    path('logout', LogoutView.as_view(), name='auth-logout'),
    path('user', MeView.as_view(), name='auth-me'),
]
