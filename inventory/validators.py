"""Shipping number checks used by the container and tracking forms."""
import re

from django.core.exceptions import ValidationError

# ISO 6346 letter values: A=10 … Z=38, skipping multiples of 11.
_LETTER_VALUES = {}
_v = 10
for _ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    if _v % 11 == 0:
        _v += 1
    _LETTER_VALUES[_ch] = _v
    _v += 1

CONTAINER_RE = re.compile(r'^[A-Z]{3}[UJZ]\d{7}$')
REFERENCE_RE = re.compile(r'^[A-Z0-9][A-Z0-9-]{4,28}[A-Z0-9]$')


def normalise(number):
    return re.sub(r'[\s/]+', '', (number or '')).upper()


def container_check_digit(first_ten):
    total = sum((_LETTER_VALUES[c] if c.isalpha() else int(c)) * 2 ** i for i, c in enumerate(first_ten))
    return total % 11 % 10


def validate_container_number(number):
    """ISO 6346: owner code (3 letters) + category U/J/Z + 6-digit serial + check digit."""
    n = normalise(number)
    if not CONTAINER_RE.match(n):
        raise ValidationError(
            f'"{n or number}" is not a container number — expected 4 letters ending in U, J or Z, '
            f'then 7 digits (e.g. MSKU1234565).')
    expected = container_check_digit(n[:10])
    if int(n[10]) != expected:
        raise ValidationError(
            f'{n} fails the container check digit — check the number on the box '
            f'(with this prefix and serial the last digit would be {expected}).')
    return n


def validate_reference_number(number, label='Bill of lading'):
    """B/L and booking numbers have no checksum; just make sure it looks like one."""
    n = normalise(number)
    has_digit = bool(re.search(r'\d', n))
    all_digits = n.replace('-', '').isdigit()
    if not REFERENCE_RE.match(n) or not has_digit or (all_digits and len(n) < 8):
        raise ValidationError(
            f'"{n or number}" does not look like a {label.lower()} number — use 6 to 30 letters/digits '
            f'as printed on the document (e.g. MATS1234567890).')
    return n


def looks_like_container(number):
    """True for anything shaped like an ISO 6346 container number, e.g. PDLU3208247."""
    return bool(CONTAINER_RE.match(normalise(number)))
