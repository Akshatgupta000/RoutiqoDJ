import datetime
from typing import Any, Dict, List, Optional, Union
from bson import ObjectId
from django.conf import settings
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

_mongo_client: Optional[MongoClient] = None
_mongo_db: Optional[Database] = None


def get_mongo_client() -> MongoClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
        )
    return _mongo_client


def get_db() -> Database:
    global _mongo_db
    if _mongo_db is None:
        client = get_mongo_client()
        _mongo_db = client[settings.MONGODB_DATABASE]
    return _mongo_db


def set_db(database: Any) -> None:
    global _mongo_db
    _mongo_db = database



class MongoCollections:
    @property
    def users(self) -> Collection:
        return get_db()['users']

    @property
    def personal_access_tokens(self) -> Collection:
        return get_db()['personal_access_tokens']

    @property
    def delivery_centers(self) -> Collection:
        return get_db()['delivery_centers']

    @property
    def vehicles(self) -> Collection:
        return get_db()['vehicles']

    @property
    def orders(self) -> Collection:
        return get_db()['orders']

    @property
    def routes(self) -> Collection:
        return get_db()['routes']

    @property
    def route_stops(self) -> Collection:
        return get_db()['route_stops']

    @property
    def service_zones(self) -> Collection:
        return get_db()['service_zones']


db = MongoCollections()


def to_object_id(val: Any) -> Any:
    """Convert value to bson.ObjectId if possible, otherwise return as is."""
    if isinstance(val, ObjectId):
        return val
    if isinstance(val, str) and ObjectId.is_valid(val):
        try:
            return ObjectId(val)
        except Exception:
            return val
    return val


def id_query(val: Any) -> Dict[str, Any]:
    """
    Returns a query dictionary matching _id either as ObjectId or string,
    ensuring 100% compatibility with Laravel MongoDB documents.
    """
    oid = to_object_id(val)
    s_val = str(val)
    if isinstance(oid, ObjectId):
        return {'_id': {'$in': [oid, s_val]}}
    return {'_id': s_val}


def foreign_id_query(field_name: str, val: Any) -> Dict[str, Any]:
    """Matches foreign keys that may be stored as ObjectId or string."""
    oid = to_object_id(val)
    s_val = str(val)
    if isinstance(oid, ObjectId):
        return {field_name: {'$in': [oid, s_val]}}
    return {field_name: s_val}


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def serialize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Serializes a MongoDB document into a JSON-friendly dict:
    - Converts _id to string 'id' and '_id'
    - Converts datetime objects to ISO-8601 strings
    - Preserves nested structures
    """
    if doc is None:
        return None

    res: Dict[str, Any] = {}
    for k, v in doc.items():
        if k == '_id':
            s_id = str(v)
            res['id'] = s_id
            res['_id'] = s_id
        elif isinstance(v, ObjectId):
            res[k] = str(v)
        elif isinstance(v, (datetime.datetime, datetime.date)):
            if isinstance(v, datetime.datetime):
                res[k] = v.isoformat()
            else:
                res[k] = v.strftime('%Y-%m-%d')
        elif isinstance(v, list):
            res[k] = [serialize_value(item) for item in v]
        elif isinstance(v, dict):
            res[k] = serialize_doc(v)
        else:
            res[k] = v

    if 'id' not in res and '_id' in res:
        res['id'] = str(res['_id'])

    return res


def serialize_value(v: Any) -> Any:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, datetime.datetime):
        return v.isoformat()
    if isinstance(v, datetime.date):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, dict):
        return serialize_doc(v)
    if isinstance(v, list):
        return [serialize_value(i) for i in v]
    return v


def serialize_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [serialize_doc(d) for d in docs if d is not None]
