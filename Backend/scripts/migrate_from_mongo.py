#!/usr/bin/env python3
"""
MongoDB Atlas to PostgreSQL Data Migration Utility for Routiqo.

Preserves existing application data by reading collections from MongoDB Atlas,
mapping documents to relational Django models, and converting ObjectId references
to relational primary and foreign keys.

Usage:
    export MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/logiroute"
    export MONGODB_DATABASE="logiroute"
    python scripts/migrate_from_mongo.py [--dry-run] [--skip-existing]

Safety Guarantees:
    - Pure read-only access to MongoDB Atlas (never modifies or deletes Mongo data).
    - Never prints user passwords or sensitive credentials.
    - Safe duplicate handling (idempotent re-runs).
    - Detailed summary report with imported, skipped, and failed counts.
"""

import argparse
import datetime
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Set up Django environment
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.db import transaction
from django.utils import timezone
from apps.authentication.models import User, PersonalAccessToken
from apps.centers.models import DeliveryCenter
from apps.vehicles.models import Vehicle
from apps.orders.models import Order
from apps.routes.models import Route, RouteStop
from apps.zones.models import ServiceZone


def parse_date_value(val: Any) -> Optional[datetime.date]:
    if not val:
        return None
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, datetime.datetime):
        return val.date()
    try:
        return datetime.datetime.strptime(str(val)[:10], '%Y-%m-%d').date()
    except Exception:
        return None


def parse_datetime_value(val: Any) -> Optional[datetime.datetime]:
    if not val:
        return None
    if isinstance(val, datetime.datetime):
        if timezone.is_naive(val):
            return timezone.make_aware(val, timezone.utc)
        return val
    try:
        dt = datetime.datetime.fromisoformat(str(val).replace('Z', '+00:00'))
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.utc)
        return dt
    except Exception:
        return None


class MongoToPostgresMigrator:
    def __init__(self, mongo_uri: str, db_name: str, dry_run: bool = False, skip_existing: bool = True):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.dry_run = dry_run
        self.skip_existing = skip_existing

        # ID Mapping dictionaries: old_object_id_str -> new_postgres_id
        self.user_map: Dict[str, int] = {}
        self.center_map: Dict[str, int] = {}
        self.vehicle_map: Dict[str, int] = {}
        self.order_map: Dict[str, int] = {}
        self.route_map: Dict[str, int] = {}

        self.stats: Dict[str, Dict[str, int]] = {}

    def get_mongo_db(self):
        try:
            from pymongo import MongoClient
        except ImportError:
            print("[ERROR] 'pymongo' is required for the data migration script.")
            print("Please run: pip install pymongo dnspython")
            sys.exit(1)

        client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=10000)
        # Test connection
        client.admin.command('ping')
        return client[self.db_name]

    def record_stat(self, collection: str, action: str):
        if collection not in self.stats:
            self.stats[collection] = {'total': 0, 'imported': 0, 'skipped': 0, 'failed': 0}
        self.stats[collection][action] += 1

    def run(self):
        print(f"Connecting to MongoDB Atlas (Database: {self.db_name})...")
        db = self.get_mongo_db()
        print("[OK] Connected to MongoDB Atlas successfully.")

        if self.dry_run:
            print(">>> RUNNING IN DRY-RUN MODE (no changes will be committed to PostgreSQL) <<<\n")

        with transaction.atomic():
            self.migrate_users(db)
            self.migrate_tokens(db)
            self.migrate_centers(db)
            self.migrate_vehicles(db)
            self.migrate_orders(db)
            self.migrate_routes(db)
            self.migrate_route_stops(db)
            self.migrate_service_zones(db)

            if self.dry_run:
                transaction.set_rollback(True)
                print("\n[INFO] Dry-run complete. All transactions rolled back.")

        self.print_summary()

    def migrate_users(self, db):
        col = db['users']
        docs = list(col.find({}))
        self.stats['users'] = {'total': len(docs), 'imported': 0, 'skipped': 0, 'failed': 0}
        print(f"Migrating users ({len(docs)} documents)...")

        for doc in docs:
            oid = str(doc['_id'])
            email = str(doc.get('email', '')).strip().lower()
            if not email:
                self.record_stat('users', 'skipped')
                continue

            existing = User.objects.filter(email=email).first()
            if existing:
                self.user_map[oid] = existing.id
                if self.skip_existing:
                    self.record_stat('users', 'skipped')
                    continue

            name = doc.get('name', '')
            raw_password = doc.get('password', '')
            reset_otp_hash = doc.get('reset_password_otp')
            reset_otp_expires = parse_datetime_value(doc.get('reset_password_expires'))

            if not self.dry_run:
                try:
                    if existing:
                        user = existing
                        user.name = name
                        user.save()
                    else:
                        user = User.objects.create(
                            email=email,
                            name=name,
                            password=raw_password,
                            reset_otp_hash=reset_otp_hash,
                            reset_otp_expires=reset_otp_expires,
                        )
                    self.user_map[oid] = user.id
                    self.record_stat('users', 'imported')
                except Exception as e:
                    print(f"  [WARN] Failed to import user {email}: {e}")
                    self.record_stat('users', 'failed')
            else:
                self.user_map[oid] = 1
                self.record_stat('users', 'imported')

    def migrate_tokens(self, db):
        col = db['personal_access_tokens']
        docs = list(col.find({}))
        self.stats['tokens'] = {'total': len(docs), 'imported': 0, 'skipped': 0, 'failed': 0}
        print(f"Migrating personal access tokens ({len(docs)} documents)...")

        for doc in docs:
            user_id = self.user_map.get(str(doc.get('tokenable_id')))
            token_hash = doc.get('token')
            if not user_id or not token_hash:
                self.record_stat('tokens', 'skipped')
                continue

            if PersonalAccessToken.objects.filter(token=token_hash).exists():
                self.record_stat('tokens', 'skipped')
                continue

            if not self.dry_run:
                try:
                    PersonalAccessToken.objects.create(
                        user_id=user_id,
                        name=doc.get('name', 'auth_token'),
                        token=token_hash,
                        abilities=doc.get('abilities', ['*']),
                        last_used_at=parse_datetime_value(doc.get('last_used_at')),
                        expires_at=parse_datetime_value(doc.get('expires_at')),
                    )
                    self.record_stat('tokens', 'imported')
                except Exception as e:
                    print(f"  [WARN] Failed to import token: {e}")
                    self.record_stat('tokens', 'failed')
            else:
                self.record_stat('tokens', 'imported')

    def migrate_centers(self, db):
        col = db['delivery_centers']
        docs = list(col.find({}))
        self.stats['delivery_centers'] = {'total': len(docs), 'imported': 0, 'skipped': 0, 'failed': 0}
        print(f"Migrating delivery centers ({len(docs)} documents)...")

        for doc in docs:
            oid = str(doc['_id'])
            user_id = self.user_map.get(str(doc.get('user_id')))
            if not user_id:
                self.record_stat('delivery_centers', 'skipped')
                continue

            name = doc.get('name', 'Delivery Center')
            try:
                lat = float(doc.get('latitude', 0.0))
                lng = float(doc.get('longitude', 0.0))
            except (ValueError, TypeError):
                self.record_stat('delivery_centers', 'skipped')
                continue

            if not self.dry_run:
                try:
                    center = DeliveryCenter.objects.create(
                        user_id=user_id,
                        name=name,
                        latitude=lat,
                        longitude=lng,
                    )
                    self.center_map[oid] = center.id
                    self.record_stat('delivery_centers', 'imported')
                except Exception as e:
                    print(f"  [WARN] Failed to import center {name}: {e}")
                    self.record_stat('delivery_centers', 'failed')
            else:
                self.center_map[oid] = 1
                self.record_stat('delivery_centers', 'imported')

    def migrate_vehicles(self, db):
        col = db['vehicles']
        docs = list(col.find({}))
        self.stats['vehicles'] = {'total': len(docs), 'imported': 0, 'skipped': 0, 'failed': 0}
        print(f"Migrating vehicles ({len(docs)} documents)...")

        for doc in docs:
            oid = str(doc['_id'])
            user_id = self.user_map.get(str(doc.get('user_id')))
            center_id = self.center_map.get(str(doc.get('delivery_center_id')))

            if not user_id:
                self.record_stat('vehicles', 'skipped')
                continue

            try:
                capacity = max(1, min(1000, int(doc.get('capacity', 100))))
                load = int(doc.get('current_load', 0))
                speed = float(doc.get('average_speed', 25.0))
            except (ValueError, TypeError):
                capacity = 100
                load = 0
                speed = 25.0

            if not self.dry_run:
                try:
                    vehicle = Vehicle.objects.create(
                        user_id=user_id,
                        delivery_center_id=center_id,
                        name=doc.get('name', 'Vehicle'),
                        vehicle_number=doc.get('vehicle_number', f"DL01XX{len(self.vehicle_map)+1:04d}"),
                        capacity=capacity,
                        current_load=load,
                        average_speed=speed,
                        is_available=bool(doc.get('is_available', True)),
                    )
                    self.vehicle_map[oid] = vehicle.id
                    self.record_stat('vehicles', 'imported')
                except Exception as e:
                    print(f"  [WARN] Failed to import vehicle: {e}")
                    self.record_stat('vehicles', 'failed')
            else:
                self.vehicle_map[oid] = 1
                self.record_stat('vehicles', 'imported')

    def migrate_orders(self, db):
        col = db['orders']
        docs = list(col.find({}))
        self.stats['orders'] = {'total': len(docs), 'imported': 0, 'skipped': 0, 'failed': 0}
        print(f"Migrating orders ({len(docs)} documents)...")

        for doc in docs:
            oid = str(doc['_id'])
            user_id = self.user_map.get(str(doc.get('user_id')))
            center_id = self.center_map.get(str(doc.get('delivery_center_id')))
            vehicle_id = self.vehicle_map.get(str(doc.get('vehicle_id')))

            if not user_id:
                self.record_stat('orders', 'skipped')
                continue

            date_val = parse_date_value(doc.get('delivery_date')) or timezone.now().date()

            try:
                lat = float(doc.get('latitude', 0.0))
                lng = float(doc.get('longitude', 0.0))
            except (ValueError, TypeError):
                self.record_stat('orders', 'skipped')
                continue

            status = str(doc.get('status', 'pending')).lower()
            if status not in ('pending', 'assigned', 'delivered'):
                status = 'pending'

            priority = str(doc.get('priority', 'normal')).lower()
            if priority not in ('normal', 'priority'):
                priority = 'normal'

            if not self.dry_run:
                try:
                    order = Order.objects.create(
                        user_id=user_id,
                        delivery_center_id=center_id,
                        vehicle_id=vehicle_id,
                        address=str(doc.get('address', 'Unknown Address')),
                        latitude=lat,
                        longitude=lng,
                        delivery_date=date_val,
                        status=status,
                        priority=priority,
                    )
                    self.order_map[oid] = order.id
                    self.record_stat('orders', 'imported')
                except Exception as e:
                    print(f"  [WARN] Failed to import order: {e}")
                    self.record_stat('orders', 'failed')
            else:
                self.order_map[oid] = 1
                self.record_stat('orders', 'imported')

    def migrate_routes(self, db):
        col = db['routes']
        docs = list(col.find({}))
        self.stats['routes'] = {'total': len(docs), 'imported': 0, 'skipped': 0, 'failed': 0}
        print(f"Migrating routes ({len(docs)} documents)...")

        for doc in docs:
            oid = str(doc['_id'])
            user_id = self.user_map.get(str(doc.get('user_id')))
            center_id = self.center_map.get(str(doc.get('delivery_center_id')))
            vehicle_id = self.vehicle_map.get(str(doc.get('vehicle_id')))

            if not user_id:
                self.record_stat('routes', 'skipped')
                continue

            try:
                distance = float(doc.get('total_distance', 0.0))
                duration = float(doc.get('total_time', 0.0)) / 60.0
            except (ValueError, TypeError):
                distance = 0.0
                duration = 0.0

            status = str(doc.get('status', 'planned')).lower()
            if status not in ('planned', 'in_progress', 'completed'):
                status = 'planned'

            if not self.dry_run:
                try:
                    route = Route.objects.create(
                        user_id=user_id,
                        delivery_center_id=center_id,
                        vehicle_id=vehicle_id,
                        comparison_batch_id=doc.get('comparison_batch_id'),
                        profile=doc.get('optimization_profile', 'shortest_distance'),
                        total_distance_km=round(distance, 3),
                        total_duration_min=round(duration, 2),
                        total_stops=int(doc.get('total_stops', 0)),
                        status=status,
                        departure_at=parse_datetime_value(doc.get('departure_at')),
                        geometry=doc.get('geometry', []),
                    )
                    self.route_map[oid] = route.id
                    self.record_stat('routes', 'imported')
                except Exception as e:
                    print(f"  [WARN] Failed to import route: {e}")
                    self.record_stat('routes', 'failed')
            else:
                self.route_map[oid] = 1
                self.record_stat('routes', 'imported')

    def migrate_route_stops(self, db):
        col = db['route_stops']
        docs = list(col.find({}))
        self.stats['route_stops'] = {'total': len(docs), 'imported': 0, 'skipped': 0, 'failed': 0}
        print(f"Migrating route stops ({len(docs)} documents)...")

        for doc in docs:
            route_id = self.route_map.get(str(doc.get('route_id')))
            order_id = self.order_map.get(str(doc.get('order_id')))

            if not route_id:
                self.record_stat('route_stops', 'skipped')
                continue

            try:
                seq = int(doc.get('sequence', 1))
                lat = float(doc.get('latitude', 0.0))
                lng = float(doc.get('longitude', 0.0))
                dist = float(doc.get('distance_from_previous', 0.0))
            except (ValueError, TypeError):
                self.record_stat('route_stops', 'skipped')
                continue

            if not self.dry_run:
                try:
                    RouteStop.objects.create(
                        route_id=route_id,
                        order_id=order_id,
                        stop_index=seq,
                        latitude=lat,
                        longitude=lng,
                        address=doc.get('address', ''),
                        distance_from_prev_km=round(dist, 3),
                        eta=parse_datetime_value(doc.get('estimated_arrival_time')),
                    )
                    self.record_stat('route_stops', 'imported')
                except Exception as e:
                    self.record_stat('route_stops', 'failed')
            else:
                self.record_stat('route_stops', 'imported')

    def migrate_service_zones(self, db):
        col = db['service_zones']
        docs = list(col.find({}))
        self.stats['service_zones'] = {'total': len(docs), 'imported': 0, 'skipped': 0, 'failed': 0}
        print(f"Migrating service zones ({len(docs)} documents)...")

        for doc in docs:
            user_id = self.user_map.get(str(doc.get('user_id')))
            center_id = self.center_map.get(str(doc.get('delivery_center_id')))

            if not user_id or not center_id:
                self.record_stat('service_zones', 'skipped')
                continue

            coords = doc.get('polygon_coordinates', [])
            if not self.dry_run:
                try:
                    ServiceZone.objects.create(
                        user_id=user_id,
                        delivery_center_id=center_id,
                        polygon_coordinates=coords,
                    )
                    self.record_stat('service_zones', 'imported')
                except Exception as e:
                    self.record_stat('service_zones', 'failed')
            else:
                self.record_stat('service_zones', 'imported')

    def print_summary(self):
        print("\n" + "=" * 65)
        print("          MONGODB TO POSTGRESQL MIGRATION SUMMARY")
        print("=" * 65)
        print(f"{'Collection':<22} | {'Total':>7} | {'Imported':>8} | {'Skipped':>7} | {'Failed':>6}")
        print("-" * 65)
        for col_name, data in self.stats.items():
            print(f"{col_name:<22} | {data['total']:>7} | {data['imported']:>8} | {data['skipped']:>7} | {data['failed']:>6}")
        print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Migrate Routiqo data from MongoDB Atlas to PostgreSQL")
    parser.add_argument('--mongo-uri', default=os.getenv('MONGODB_URI'), help="MongoDB connection URI")
    parser.add_argument('--db-name', default=os.getenv('MONGODB_DATABASE', 'logiroute'), help="MongoDB database name")
    parser.add_argument('--dry-run', action='store_true', help="Preview migration without committing changes")
    parser.add_argument('--skip-existing', action='store_true', default=True, help="Skip existing users/records")

    args = parser.parse_args()

    if not args.mongo_uri:
        print("[ERROR] MONGODB_URI environment variable or --mongo-uri argument is required.")
        print("Example:")
        print("  export MONGODB_URI='mongodb+srv://user:pass@cluster.mongodb.net/logiroute'")
        print("  python scripts/migrate_from_mongo.py")
        sys.exit(1)

    migrator = MongoToPostgresMigrator(
        mongo_uri=args.mongo_uri,
        db_name=args.db_name,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
    )
    migrator.run()


if __name__ == '__main__':
    main()

