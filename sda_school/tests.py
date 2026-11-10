from django.test import TestCase
from django.urls import reverse

from .models import Enquiry

PAGES = ['home', 'about', 'academics', 'spiritual_life', 'admissions', 'news', 'contact']


class SchoolSiteTests(TestCase):
    def test_pages_are_public(self):
        for name in PAGES:
            with self.subTest(page=name):
                resp = self.client.get(reverse(f'sda_school:{name}'))
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, 'Seventh-day Adventist School')

    def test_lives_under_sda_school(self):
        self.assertEqual(reverse('sda_school:home'), '/sda_school/')
        self.assertEqual(reverse('sda_school:contact'), '/sda_school/contact/')

    def test_enquiry_is_saved(self):
        resp = self.client.post(reverse('sda_school:contact'), {
            'name': 'Sina Tuilagi', 'email': 'sina@example.com', 'topic': 'visit',
            'level': 'primary', 'message': 'We would like to visit.',
        })
        self.assertRedirects(resp, '/sda_school/contact/#enquire', fetch_redirect_response=False)
        self.assertEqual(Enquiry.objects.get().topic, 'visit')

    def test_invalid_enquiry_shows_errors(self):
        resp = self.client.post(reverse('sda_school:admissions'), {'name': '', 'email': 'bad', 'message': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Enquiry.objects.exists())

    def test_honeypot_drops_spam(self):
        self.client.post(reverse('sda_school:contact'), {
            'name': 'Bot', 'email': 'bot@example.com', 'topic': 'general',
            'message': 'spam', 'website': 'http://spam.example',
        })
        self.assertFalse(Enquiry.objects.exists())
