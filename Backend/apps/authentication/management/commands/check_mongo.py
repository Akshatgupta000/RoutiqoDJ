import re
from django.core.management.base import BaseCommand
from django.conf import settings
from core.database import check_mongo_connection, get_db, get_mongo_client


class Command(BaseCommand):
    help = 'Check MongoDB connection and verify database access'

    def handle(self, *args, **options):
        uri = getattr(settings, 'MONGODB_URI', '')
        # Redact password in URI
        redacted_uri = re.sub(r':([^:@]+)@', ':****@', uri)
        db_name = getattr(settings, 'MONGODB_DATABASE', 'logiroute')

        self.stdout.write(self.style.NOTICE(f"Connecting to MongoDB at: {redacted_uri}"))
        self.stdout.write(self.style.NOTICE(f"Target Database: {db_name}"))

        success, error_msg = check_mongo_connection()

        if success:
            self.stdout.write(self.style.SUCCESS("[OK] Successfully connected to MongoDB Atlas!"))
            try:
                client = get_mongo_client()
                db = get_db()
                collections = db.list_collection_names()
                self.stdout.write(self.style.SUCCESS(f"[OK] Database '{db_name}' collections: {collections}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"[WARN] Connected, but error listing collections: {e}"))
        else:
            self.stdout.write(self.style.ERROR(f"[FAIL] MongoDB connection failed:\n  {error_msg}"))
            self.stdout.write(self.style.WARNING(
                "\nTroubleshooting tips:\n"
                "  1. Check that MONGODB_URI in Backend/.env has the correct username and password.\n"
                "  2. Check that your current IP address is whitelisted in MongoDB Atlas Network Access (0.0.0.0/0 for anywhere).\n"
                "  3. Verify dnspython is installed for mongodb+srv:// resolution."
            ))
            exit(1)

