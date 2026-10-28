from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Send a test email with the configured backend (Office 365 once MS_GRAPH_* settings are set).'

    def add_arguments(self, parser):
        parser.add_argument('to', help='Address to send the test email to.')

    def handle(self, *args, **options):
        self.stdout.write(f'Backend: {settings.EMAIL_BACKEND}\nFrom: {settings.DEFAULT_FROM_EMAIL}')
        send_mail('Ah Liki IMS test email',
                  'If you can read this, email from Ah Liki IMS is working.',
                  None, [options['to']])
        self.stdout.write(self.style.SUCCESS(f'Sent to {options["to"]}.'))
