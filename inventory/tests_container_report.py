from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from . import scheduler
from .container_report import send_report
from .models import CmsContainer, ScheduledRun, ShippingLine, Yard


@override_settings(CONTAINER_REPORT_RECIPIENTS=['boss@example.com'], CONTAINER_REPORT_TIME='07:00',
                   SITE_URL='https://ims.example.com',
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ContainerReportTests(TestCase):
    def setUp(self):
        swire = ShippingLine.objects.get(name='SWIRE')
        swire.return_days = 10
        swire.save()
        hq = Yard.objects.get(code='HQ-ALW-VAI')
        today = timezone.localdate()
        CmsContainer.objects.create(code='LATE1234567', yard=hq, status='full', owner=swire,
                                    arrival_date=today - timedelta(days=15))
        CmsContainer.objects.create(code='SOON1234567', yard=hq, status='empty', owner=swire,
                                    arrival_date=today - timedelta(days=7))

    def test_report_lists_overdue_and_due_soon_with_csv(self):
        send_report()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['boss@example.com'])
        self.assertIn('1 overdue', msg.subject)
        html = msg.alternatives[0][0]
        self.assertIn('LATE1234567', html)
        self.assertIn('5 days', html)
        self.assertIn('SOON1234567', html)
        self.assertIn('https://ims.example.com/cms/', html)
        name, content, mimetype = msg.attachments[0]
        self.assertEqual(mimetype, 'text/csv')
        self.assertIn('LATE1234567', content)

    @override_settings(CONTAINER_REPORT_RECIPIENTS=[])
    def test_no_recipients_sends_nothing(self):
        self.assertIn('Skipped', send_report())
        self.assertEqual(len(mail.outbox), 0)

    def test_scheduler_sends_once_a_day_after_the_time(self):
        early = timezone.localtime().replace(hour=6, minute=59)
        self.assertFalse(scheduler.is_due('07:00', early))
        self.assertTrue(scheduler.is_due('07:00', early.replace(hour=7, minute=0)))
        self.assertFalse(scheduler.is_due('', early.replace(hour=23)))

        self.assertIsNotNone(scheduler.run_once_today('container_report', send_report))
        self.assertIsNone(scheduler.run_once_today('container_report', send_report))
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(ScheduledRun.objects.get(job='container_report').result.startswith('Sent to'))

    def test_failed_send_is_retried(self):
        def boom():
            raise RuntimeError('mail down')
        with self.assertRaises(RuntimeError):
            scheduler.run_once_today('container_report', boom)
        self.assertFalse(ScheduledRun.objects.exists())
        scheduler.run_once_today('container_report', send_report)
        self.assertEqual(len(mail.outbox), 1)
