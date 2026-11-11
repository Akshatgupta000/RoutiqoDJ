from django.urls import path
from apps.vehicles.views import VehicleListCreateView, VehicleDetailView, VehicleResetFleetView

urlpatterns = [
    path('vehicles', VehicleListCreateView.as_view(), name='vehicles-list-create'),
    path('vehicles/reset-fleet', VehicleResetFleetView.as_view(), name='vehicles-reset-fleet'),
    path('vehicles/<str:id>', VehicleDetailView.as_view(), name='vehicles-detail'),
]
