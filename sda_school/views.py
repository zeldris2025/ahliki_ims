from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render

from . import content
from .forms import EnquiryForm


def _dated(items):
    return [{**item, 'date': date.fromisoformat(item['date'])} for item in items]


def _page(request, template, **extra):
    """Render a school page with the shared school details and navigation."""
    ctx = {
        'school': content.SCHOOL,
        'nav': content.NAV,
        'adventist_links': content.ADVENTIST_LINKS,
        'sabbath_note': content.SABBATH_NOTE,
        'year': date.today().year,
    }
    ctx.update(extra)
    return render(request, f'sda_school/{template}', ctx)


def _enquiry_form(request, initial=None):
    """Return (form, redirect) — a redirect after a successful submission, else None."""
    if request.method != 'POST':
        return EnquiryForm(initial=initial), None
    form = EnquiryForm(request.POST)
    if form.is_valid():
        if not form.is_spam():
            form.save()
        messages.success(request, 'Thank you! Your message has been received. '
                                  'Our office will reply within two working days.')
        return form, redirect(request.path + '#enquire')
    return form, None


def home(request):
    today = date.today()
    events = [e for e in _dated(content.EVENTS) if e['date'] >= today][:3]
    return _page(request, 'home.html', page='home',
                 stats=content.STATS, values=content.VALUES, programs=content.PROGRAMS,
                 spiritual=content.SPIRITUAL_LIFE[:3], news=_dated(content.NEWS),
                 events=events, testimonials=content.TESTIMONIALS)


def about(request):
    return _page(request, 'about.html', page='about', title='About Us',
                 mission=content.MISSION, vision=content.VISION, values=content.VALUES,
                 leadership=content.LEADERSHIP, beliefs=content.BELIEFS)


def academics(request):
    return _page(request, 'academics.html', page='academics', title='Academics',
                 programs=content.PROGRAMS, subjects=content.SUBJECTS)


def spiritual_life(request):
    return _page(request, 'spiritual_life.html', page='spiritual_life', title='Spiritual Life',
                 spiritual=content.SPIRITUAL_LIFE, beliefs=content.BELIEFS)


def admissions(request):
    form, done = _enquiry_form(request, initial={'topic': 'admissions'})
    if done:
        return done
    return _page(request, 'admissions.html', page='admissions', title='Admissions',
                 steps=content.ADMISSION_STEPS, documents=content.ADMISSION_DOCUMENTS,
                 faqs=content.FAQS, form=form)


def news(request):
    today = date.today()
    events = [e for e in _dated(content.EVENTS) if e['date'] >= today]
    return _page(request, 'news.html', page='news', title='News & Events',
                 news=_dated(content.NEWS), events=events)


def contact(request):
    topic = request.GET.get('topic', 'general')
    form, done = _enquiry_form(request, initial={'topic': topic})
    if done:
        return done
    return _page(request, 'contact.html', page='contact', title='Contact Us', form=form)
