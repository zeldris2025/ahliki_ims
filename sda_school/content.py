"""Everything the school website says about the school, in one place.

Edit the name, contact details, numbers, staff and news here; the templates read
from these values and do not need changing. Items marked SAMPLE are placeholder
text written for the first version of the site — replace them with the school's
real details before going live.
"""

SCHOOL = {
    'name': 'SDA School',                       # SAMPLE — the school's full name
    'short_name': 'SDA School',
    'full_title': 'Seventh-day Adventist School',
    'location': 'Apia, Samoa',                   # SAMPLE
    'motto': 'Educating for Eternity',           # SAMPLE
    'tagline': 'Faith. Excellence. Service.',
    'founded': 1975,                             # SAMPLE
    'phone': '(+685) 00000',                     # SAMPLE
    'email': 'info@sdaschool.ws',                # SAMPLE
    'address': 'Main Road, Apia, Samoa',         # SAMPLE
    'office_hours': 'Monday – Thursday 8:00am – 4:30pm · Friday 8:00am – 1:00pm',
    'map_query': 'Apia, Samoa',
    'facebook': '',                              # full URLs; leave blank to hide the icon
    'instagram': '',
    'youtube': '',
}

# Numbers shown in the stats strip on the home page. SAMPLE
STATS = [
    {'value': '50+', 'label': 'Years of Adventist education'},
    {'value': '600', 'label': 'Students, ECE to Year 13'},
    {'value': '45', 'label': 'Dedicated teachers & staff'},
    {'value': '98%', 'label': 'National exam pass rate'},
]

# The school's purpose, drawn from the aims of Adventist education.
MISSION = ('To lead every student into a saving relationship with Jesus Christ and to develop '
           'the whole person — mind, body and spirit — for a life of joyful service to God, '
           'family and community.')
VISION = ('A Christ-centred community of learning where every child is known, valued and '
          'equipped to make a difference in Samoa and the world.')

VALUES = [
    {'icon': 'heart', 'title': 'Faith', 'text': 'Daily worship, Bible study and prayer place Jesus at the centre of school life.'},
    {'icon': 'star', 'title': 'Excellence', 'text': 'High academic expectations, supported by caring teachers and small classes.'},
    {'icon': 'hands', 'title': 'Service', 'text': 'Students learn to serve through community outreach and mission projects.'},
    {'icon': 'leaf', 'title': 'Wholeness', 'text': 'Healthy living, sport and the arts balance the growth of mind, body and spirit.'},
]

PROGRAMS = [
    {
        'slug': 'early-childhood', 'icon': 'sprout', 'title': 'Early Childhood',
        'ages': 'Ages 3 – 5', 'summary': 'A gentle, play-based start where little ones discover God’s world, '
        'build early literacy and numeracy, and grow in confidence.',
        'points': ['Play-based learning', 'Bilingual Samoan & English', 'Bible stories & songs', 'Safe, nurturing classrooms'],
    },
    {
        'slug': 'primary', 'icon': 'book', 'title': 'Primary School',
        'ages': 'Years 1 – 8', 'summary': 'Strong foundations in reading, writing, mathematics and science, '
        'taught alongside character, creativity and faith.',
        'points': ['National curriculum', 'Reading recovery support', 'Music, art & PE', 'Junior Pathfinders'],
    },
    {
        'slug': 'secondary', 'icon': 'cap', 'title': 'Secondary College',
        'ages': 'Years 9 – 13', 'summary': 'Rigorous preparation for national examinations, university and '
        'careers, with leadership opportunities in a supportive Christian setting.',
        'points': ['SSC & SPFSC pathways', 'Science & computing labs', 'Career guidance', 'Student leadership'],
    },
]

SUBJECTS = [
    'English', 'Samoan', 'Mathematics', 'Biology', 'Chemistry', 'Physics',
    'Computer Studies', 'Accounting', 'Economics', 'Geography', 'History',
    'Religious Studies', 'Health & Physical Education', 'Music', 'Visual Arts', 'Agriculture',
]

SPIRITUAL_LIFE = [
    {'icon': 'sun', 'title': 'Morning Worship', 'text': 'Each school day begins with worship, prayer and a short devotional in every classroom.'},
    {'icon': 'chapel', 'title': 'Weekly Chapel', 'text': 'Whole-school chapel services with student-led music, testimonies and guest speakers.'},
    {'icon': 'compass', 'title': 'Pathfinders & Adventurers', 'text': 'Outdoor skills, honours and service through the Adventist youth clubs.'},
    {'icon': 'globe', 'title': 'Mission & Outreach', 'text': 'Community service days, village visits and mission trips put faith into action.'},
    {'icon': 'book', 'title': 'Week of Prayer', 'text': 'Special spiritual emphasis weeks each term, with opportunities for baptism classes.'},
    {'icon': 'music', 'title': 'Choir & Music Ministry', 'text': 'Choirs and ensembles that lead worship at school and in local churches.'},
]

# The hours of the Sabbath are kept free from school activities.
SABBATH_NOTE = ('As a Seventh-day Adventist school we honour the Sabbath. The office is closed from '
                'Friday sunset to Saturday sunset, and no school events are held during those hours.')

ADMISSION_STEPS = [
    {'title': 'Enquire', 'text': 'Send an enquiry online or call the office. We will answer your questions and send the enrolment pack.'},
    {'title': 'Visit', 'text': 'Book a campus tour to meet our teachers, see the classrooms and feel the school community.'},
    {'title': 'Apply', 'text': 'Complete the enrolment form and bring the required documents to the school office.'},
    {'title': 'Interview', 'text': 'Meet with the Principal or Deputy. Older students may sit a short placement assessment.'},
    {'title': 'Welcome', 'text': 'Receive your offer letter, uniform list and start date — welcome to the family!'},
]

ADMISSION_DOCUMENTS = [
    'Completed enrolment form',
    'Birth certificate (copy)',
    'Most recent school report',
    'Immunisation record',
    'Two passport-size photos',
    'Transfer letter from previous school (Year 2 and above)',
]

FAQS = [
    {'q': 'Do you accept students who are not Seventh-day Adventist?',
     'a': 'Yes. Families of every faith background are welcome. All students take part in worship and '
          'Religious Studies, which are part of our Christian education.'},
    {'q': 'When does the school year start?',
     'a': 'The school year begins in late January. We accept enrolments throughout the year where places are available.'},
    {'q': 'What are the school fees?',
     'a': 'Fees depend on the year level. Please contact the office for the current fee schedule; '
          'sibling discounts and payment plans are available.'},
    {'q': 'Is there a school uniform?',
     'a': 'Yes. Uniforms are available from the school office. The full uniform list is included in the enrolment pack.'},
    {'q': 'Why is there no school activity on Saturday?',
     'a': 'Saturday is the Sabbath, a day of rest and worship. Sport, events and homework deadlines are never set on the Sabbath.'},
]

# SAMPLE — replace with real news. Dates are ISO strings (YYYY-MM-DD).
NEWS = [
    {'date': '2026-11-02', 'category': 'Achievement', 'title': 'Year 13 students sit national examinations',
     'text': 'Our senior students completed their final examinations this week. We are proud of their hard work and pray for every one of them.'},
    {'date': '2026-10-20', 'category': 'Spiritual Life', 'title': 'Week of Prayer brings the school together',
     'text': 'Students and staff gathered each morning for worship, music and messages on the theme “Called to Serve”.'},
    {'date': '2026-10-05', 'category': 'Community', 'title': 'Pathfinders lead village clean-up day',
     'text': 'Our Pathfinder club partnered with local families to clean beaches and plant trees as part of community service.'},
]

EVENTS = [
    {'date': '2026-11-20', 'title': 'Prize Giving Ceremony', 'time': '9:00am', 'place': 'School Hall'},
    {'date': '2026-11-27', 'title': 'Graduation Service', 'time': '5:00pm', 'place': 'Church Auditorium'},
    {'date': '2026-12-04', 'title': 'Last day of Term 4', 'time': 'All day', 'place': 'Campus'},
    {'date': '2027-01-26', 'title': 'Term 1 begins — Welcome back!', 'time': '8:00am', 'place': 'Campus'},
]

# SAMPLE — replace with real quotes, used with permission.
TESTIMONIALS = [
    {'quote': 'The teachers know my children by name and care about who they are becoming, not just their grades.',
     'who': 'Parent', 'detail': 'Primary School family'},
    {'quote': 'Leading worship and serving in the community gave me confidence I never knew I had.',
     'who': 'Head Student', 'detail': 'Year 13'},
    {'quote': 'It is a privilege to teach where faith and learning grow side by side every day.',
     'who': 'Teacher', 'detail': 'Secondary Science'},
]

# SAMPLE — leadership roles; add names when ready.
LEADERSHIP = [
    {'role': 'Principal', 'name': '', 'text': 'Leads the school’s academic and spiritual vision.'},
    {'role': 'Deputy Principal', 'name': '', 'text': 'Oversees curriculum, teaching and student achievement.'},
    {'role': 'Chaplain', 'name': '', 'text': 'Cares for the spiritual life of students, families and staff.'},
    {'role': 'Board Chair', 'name': '', 'text': 'Chairs the school board on behalf of the church.'},
]

# Short summary of what Seventh-day Adventists believe, linking to the church's own pages.
BELIEFS = [
    {'title': 'The Bible', 'text': 'Scripture is God’s inspired word and the foundation of everything we teach.'},
    {'title': 'Salvation in Jesus', 'text': 'Through Christ’s life, death and resurrection, God offers salvation to all.'},
    {'title': 'The Sabbath', 'text': 'The seventh day is a gift of rest, worship and fellowship with God and family.'},
    {'title': 'Second Coming', 'text': 'We share the blessed hope of Jesus’ soon return.'},
    {'title': 'Healthy Living', 'text': 'Our bodies are temples of the Holy Spirit, cared for through wise choices.'},
    {'title': 'Service', 'text': 'We are called to share God’s love by serving others.'},
]

ADVENTIST_LINKS = [
    {'label': 'Seventh-day Adventist Church', 'url': 'https://www.adventist.org/'},
    {'label': '28 Fundamental Beliefs', 'url': 'https://www.adventist.org/beliefs/'},
    {'label': 'Adventist Education', 'url': 'https://adventisteducation.org/'},
]

NAV = [
    ('sda_school:home', 'Home'),
    ('sda_school:about', 'About'),
    ('sda_school:academics', 'Academics'),
    ('sda_school:spiritual_life', 'Spiritual Life'),
    ('sda_school:admissions', 'Admissions'),
    ('sda_school:news', 'News & Events'),
    ('sda_school:contact', 'Contact'),
]
