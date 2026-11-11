from django.urls import path
from apps.zones.views import (
    ServiceZoneListView,
    ServiceZoneGenerateView,
    ServiceZoneCheckView,
)

urlpatterns = [
    path('zones', ServiceZoneListView.as_view(), name='zones-list'),
    path('zones/generate', ServiceZoneGenerateView.as_view(), name='zones-generate'),
    path('zones/check', ServiceZoneCheckView.as_view(), name='zones-check'),
]

