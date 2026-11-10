from django.db import models


class Enquiry(models.Model):
    """A message sent from the school website's contact or admissions form."""

    TOPIC_CHOICES = [
        ('admissions', 'Admissions & enrolment'),
        ('visit', 'Book a campus visit'),
        ('general', 'General enquiry'),
        ('fees', 'Fees & payments'),
    ]
    LEVEL_CHOICES = [
        ('', 'Not applicable'),
        ('ece', 'Early Childhood (ages 3–5)'),
        ('primary', 'Primary (Years 1–8)'),
        ('secondary', 'Secondary (Years 9–13)'),
    ]

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    topic = models.CharField(max_length=20, choices=TOPIC_CHOICES, default='general')
    level = models.CharField('year level of interest', max_length=20, choices=LEVEL_CHOICES, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False, help_text='Tick once someone has replied.')

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'enquiries'

    def __str__(self):
        return f'{self.name} — {self.get_topic_display()}'
