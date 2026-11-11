from django.urls import path, include
from django.http import JsonResponse


def root_health(request):
    return JsonResponse({'status': 'Routiqo Backend Running'})


def up_health(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    # Health checks
    path('', root_health, name='root-health'),
    path('up', up_health, name='up-health'),
    path('api/up', up_health, name='api-up-health'),

    # API endpoints
    path('api/', include('apps.authentication.urls')),
    path('api/', include('apps.centers.urls')),
    path('api/', include('apps.vehicles.urls')),
    path('api/', include('apps.orders.urls')),
    path('api/', include('apps.routes.urls')),
    path('api/', include('apps.zones.urls')),
]

