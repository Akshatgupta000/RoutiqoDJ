from typing import Any, Dict, List, Optional
from rest_framework.exceptions import NotFound, ValidationError
from core.helpers import is_point_in_polygon
from core.serializers import format_delivery_center
from apps.zones.models import ServiceZone
from apps.centers.models import DeliveryCenter


def format_service_zone(zone: Any, center: Optional[Any] = None) -> Dict[str, Any]:
    z_id = str(getattr(zone, 'id', ''))
    dc_id = str(getattr(zone, 'delivery_center_id', ''))
    if center is None and dc_id:
        center = getattr(zone, 'delivery_center', None) or DeliveryCenter.objects.filter(id=dc_id).first()
    return {
        'id': z_id,
        'delivery_center_id': dc_id,
        'polygon_coordinates': getattr(zone, 'polygon_coordinates', []),
        'delivery_center': format_delivery_center(center) if center else None,
    }


def list_zones(user_id: Any) -> List[Dict[str, Any]]:
    zones = ServiceZone.objects.filter(user_id=user_id).select_related('delivery_center').order_by('id')
    return [format_service_zone(z, z.delivery_center) for z in zones]


def save_zones(user_id: Any, zones_data: List[Dict[str, Any]]) -> None:
    if not isinstance(zones_data, list):
        raise ValidationError({'zones': ['The zones field must be an array.']})

    for idx, item in enumerate(zones_data):
        if not isinstance(item, dict) or 'hub_id' not in item or 'polygon' not in item:
            raise ValidationError({'zones': [f'Zone at index {idx} must have hub_id and polygon.']})

    # Clear old zones and save new ones
    ServiceZone.objects.filter(user_id=user_id).delete()

    new_zones = []
    for item in zones_data:
        hub_id = item['hub_id']
        polygon = item['polygon']
        new_zones.append(
            ServiceZone(
                user_id=user_id,
                delivery_center_id=hub_id,
                polygon_coordinates=polygon,
            )
        )

    if new_zones:
        ServiceZone.objects.bulk_create(new_zones)


def check_coordinates(user_id: Any, lat: float, lng: float) -> Optional[Dict[str, Any]]:
    zones = ServiceZone.objects.filter(user_id=user_id).select_related('delivery_center')
    for zone in zones:
        coords = zone.polygon_coordinates or []
        if is_point_in_polygon(lat, lng, coords):
            return {
                'hub_id': str(zone.delivery_center_id),
                'zone': format_service_zone(zone, zone.delivery_center),
            }
    return None
