"""
Management command to setup and sync MongoDB.
Usage: python manage.py setup_mongodb
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Setup MongoDB: create indexes and sync all data from Django ORM'

    def add_arguments(self, parser):
        parser.add_argument(
            '--indexes-only',
            action='store_true',
            help='Only create indexes, do not sync data',
        )

    def handle(self, *args, **options):
        from converter.mongodb import is_connected, ensure_indexes, full_sync_from_django

        self.stdout.write('Checking MongoDB connection...')

        if not is_connected():
            self.stdout.write(self.style.ERROR(
                'MongoDB is not available. Please ensure MongoDB is running on '
                'the configured URI and try again.'
            ))
            return

        self.stdout.write(self.style.SUCCESS('MongoDB connection OK!'))

        # Create indexes
        self.stdout.write('Creating MongoDB indexes...')
        ensure_indexes()
        self.stdout.write(self.style.SUCCESS('Indexes created.'))

        if options['indexes_only']:
            self.stdout.write(self.style.SUCCESS('Done (indexes only).'))
            return

        # Full sync
        self.stdout.write('Syncing all data from Django ORM to MongoDB...')
        success = full_sync_from_django()
        if success:
            self.stdout.write(self.style.SUCCESS(
                'Full sync completed! All data is now in MongoDB "pdftools" database.'
            ))
        else:
            self.stdout.write(self.style.ERROR('Sync failed. Check logs.'))
