from typing import Any, Dict, List, Optional
from rest_framework.exceptions import NotFound, ValidationError
from core.database import db, now_utc, id_query, to_object_id
from core.helpers import is_point_in_polygon
from core.serializers import format_delivery_center


def format_service_zone(zone: Dict[str, Any], center: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    z_id = str(zone.get('id', zone.get('_id', '')))
    dc_id = str(zone.get('delivery_center_id', ''))
    if center is None and dc_id:
        center = db.delivery_centers.find_one(id_query(dc_id))
    return {
        'id': z_id,
        'delivery_center_id': dc_id,
        'polygon_coordinates': zone.get('polygon_coordinates', []),
        'delivery_center': format_delivery_center(center) if center else None,
    }


def list_zones(user_id: str) -> List[Dict[str, Any]]:
    zones = list(db.service_zones.find({'user_id': str(user_id)}))
    center_ids = [z.get('delivery_center_id') for z in zones if z.get('delivery_center_id')]
    centers_map = {}
    if center_ids:
        c_docs = db.delivery_centers.find({
            '$or': [
                {'_id': {'$in': [to_object_id(cid) for cid in center_ids]}},
                {'_id': {'$in': [str(cid) for cid in center_ids]}},
            ]
        })
        for c in c_docs:
            centers_map[str(c['_id'])] = c

    return [format_service_zone(z, centers_map.get(str(z.get('delivery_center_id')))) for z in zones]


def save_zones(user_id: str, zones_data: List[Dict[str, Any]]) -> None:
    if not isinstance(zones_data, list):
        raise ValidationError({'zones': ['The zones field must be an array.']})

    for idx, item in enumerate(zones_data):
        if not isinstance(item, dict) or 'hub_id' not in item or 'polygon' not in item:
            raise ValidationError({'zones': [f'Zone at index {idx} must have hub_id and polygon.']})

    # Clear old zones and save new ones (deterministic replacement)
    db.service_zones.delete_many({'user_id': str(user_id)})

    new_docs = []
    for item in zones_data:
        new_docs.append({
            'user_id': str(user_id),
            'delivery_center_id': str(item['hub_id']),
            'polygon_coordinates': item['polygon'],
            'created_at': now_utc(),
            'updated_at': now_utc(),
        })

    if new_docs:
        db.service_zones.insert_many(new_docs)


def check_coordinates(user_id: str, lat: float, lng: float) -> Optional[Dict[str, Any]]:
    zones = list(db.service_zones.find({'user_id': str(user_id)}))
    for zone in zones:
        coords = zone.get('polygon_coordinates', [])
        if is_point_in_polygon(lat, lng, coords):
            center_doc = db.delivery_centers.find_one(id_query(zone.get('delivery_center_id')))
            return {
                'hub_id': str(zone.get('delivery_center_id')),
                'zone': format_service_zone(zone, center_doc),
            }
    return None

