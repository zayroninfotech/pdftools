from django.core.management.base import BaseCommand
from converter.models import CustomUser


class Command(BaseCommand):
    help = 'Create the default superadmin user (username: 2812, role: superadmin)'

    def handle(self, *args, **options):
        username = '2812'
        password = 'S@isatya204'
        email = 'superadmin@zayroninfotech.com'

        if CustomUser.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f'Superadmin user "{username}" already exists. Skipping creation.'
            ))
            return

        user = CustomUser.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name='Super',
            last_name='Admin',
            role='superadmin',
            is_staff=True,
            is_superuser=True,
        )

        self.stdout.write(self.style.SUCCESS(
            f'Superadmin created successfully!\n'
            f'  Username: {username}\n'
            f'  Password: {password}\n'
            f'  Email: {email}\n'
            f'  Role: superadmin'
        ))
