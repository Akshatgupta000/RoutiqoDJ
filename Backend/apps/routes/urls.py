from django.urls import path
from apps.routes.views import (
    RouteListGenerateView,
    RouteDetailView,
    RouteRegenerateView,
    RouteClearView,
    RouteForVehicleView,
)

urlpatterns = [
    path('routes', RouteListGenerateView.as_view(), name='routes-list'),
    path('routes/generate', RouteListGenerateView.as_view(), name='routes-generate'),
    path('routes/clear', RouteClearView.as_view(), name='routes-clear'),
    path('routes/<str:id>', RouteDetailView.as_view(), name='routes-detail'),
    path('routes/regenerate/<str:center_id>', RouteRegenerateView.as_view(), name='routes-regenerate'),
    path('routes/vehicle/<str:vehicle_id>/generate', RouteForVehicleView.as_view(), name='routes-vehicle-generate'),
]

