from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Verify database connection and display database status'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Testing database connection..."))
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
                try:
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()[0]
                except Exception:
                    version = "SQLite/Other"
                try:
                    cursor.execute("SELECT current_database(), current_user;")
                    db_name, db_user = cursor.fetchone()
                except Exception:
                    db_name, db_user = connection.settings_dict.get('NAME'), connection.settings_dict.get('USER')

            self.stdout.write(self.style.SUCCESS("[OK] Database connected successfully!"))
            self.stdout.write(self.style.SUCCESS(f"  Database: {db_name}"))
            self.stdout.write(self.style.SUCCESS(f"  User:     {db_user}"))
            self.stdout.write(self.style.SUCCESS(f"  Engine:   {connection.settings_dict.get('ENGINE')}"))
            self.stdout.write(self.style.SUCCESS(f"  Version:  {version}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[FAIL] Database connection failed:\n  {e}"))
            exit(1)

