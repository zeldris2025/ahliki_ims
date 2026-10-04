"""Catalogue matching for uploaded invoice line items.

An invoice line carries three things we can check against the product
catalogue: the SKU, the description and the unit of measure. This module
compares all three and reports which of them agree, so the person uploading
the invoice can see *why* a line matched (or did not) before it becomes a
tracked line item.

Two facts about the Ah Liki catalogue shape the logic here:

* Catalogue SKUs are truncated name slugs (``TANUMAPUA-FRESH-EGGS-4``), not
  supplier codes. The ``AL10002942`` codes printed on the invoice do not appear
  in the catalogue at all, so a SKU that "differs" is the normal case and is
  reported as *not recorded* rather than as a mismatch.
* Around a third of products share their name with another product
  (``Tanumapua Fresh Eggs Large 15X1Doz`` exists as both ``5pack`` and
  ``case15``). The unit — including its pack count — is what tells them apart,
  so units are compared as (measure, count) and not folded together.
"""

import re
from bisect import bisect_left
from collections import defaultdict
from difflib import SequenceMatcher

from .models import Product

# Units printed on Ah Liki invoices vs. the wording used in the catalogue.
UNIT_ALIASES = {
    'ea': 'each', 'each': 'each', 'pc': 'each', 'pcs': 'each', 'piece': 'each',
    'unit': 'each', 'no': 'each',
    'case': 'case', 'cse': 'case', 'ctn': 'case', 'carton': 'case',
    'box': 'case', 'bx': 'case',
    'pkt': 'pack', 'pk': 'pack', 'pack': 'pack', 'packet': 'pack',
    'bag': 'bag', 'bg': 'bag', 'sack': 'bag',
    'btl': 'bottle', 'bottle': 'bottle',
    'tin': 'tin', 'can': 'tin',
    'kg': 'kg', 'kgs': 'kg', 'kilo': 'kg', 'kilogram': 'kg',
    'g': 'g', 'gm': 'g', 'gram': 'g',
    'lb': 'pound', 'pound': 'pound',
    'l': 'litre', 'lt': 'litre', 'ltr': 'litre', 'litre': 'litre', 'liter': 'litre',
    'ml': 'ml',
    'doz': 'dozen', 'dz': 'dozen', 'dozen': 'dozen',
    'roll': 'roll', 'rl': 'roll',
    'set': 'set', 'pair': 'pair', 'tray': 'tray', 'drum': 'drum',
}

# The supplier codes printed on Ah Liki invoices, e.g. AL10002942.
INVOICE_SKU_RE = re.compile(r'^AL\d+$', re.IGNORECASE)

# A description has to be at least this similar to count as a fuzzy match.
FUZZY_THRESHOLD = 0.82

# Catalogue names often carry a trailing code or qualifier the invoice omits
# ("… (516)", "… - 17909", "… (EXPORT)"). When the invoice description is a
# whole-word prefix of the catalogue one, the remainder is ignored and the
# descriptions count as matching. Very short descriptions are excluded, because
# a two-letter prefix would match half the catalogue.
MIN_PREFIX_CHARS = 12

# How many index candidates to run the (expensive) similarity check against.
MAX_FUZZY_CANDIDATES = 60


def looks_like_invoice_sku(value):
    return bool(INVOICE_SKU_RE.match((value or '').strip()))


def parse_unit(value):
    """Split a unit of measure into (measure, count).

    ``case15`` → ``('case', 15)``, ``6pack`` → ``('pack', 6)``,
    ``25 KG`` → ``('kg', 25)``, ``CASE`` → ``('case', None)``.
    The count is what separates two catalogue products that share a name, so it
    is kept rather than stripped.
    """
    value = (value or '').strip().lower()
    if not value:
        return '', None
    letters = re.sub(r'[^a-z]', '', value)
    digits = re.findall(r'\d+', value)
    count = int(digits[0]) if digits else None
    if not letters:
        return '', count
    if letters.endswith('s') and letters[:-1] in UNIT_ALIASES:
        letters = letters[:-1]
    return UNIT_ALIASES.get(letters, letters), count


def normalise_unit(value):
    """Canonical measure only, ignoring the pack count."""
    return parse_unit(value)[0]


def compare_units(invoice_unit, catalogue_unit):
    """Return 'match' | 'close' | 'differs' | 'unknown' for two units."""
    inv_measure, inv_count = parse_unit(invoice_unit)
    cat_measure, cat_count = parse_unit(catalogue_unit)
    if not inv_measure or not cat_measure:
        return 'unknown'
    if inv_measure != cat_measure:
        return 'differs'
    # Same measure — the pack count decides, when both sides state one.
    if inv_count is not None and cat_count is not None and inv_count != cat_count:
        return 'close'
    return 'match'


def normalise_text(value):
    """Lower-case, collapse punctuation/whitespace so descriptions compare fairly.

    Capitalisation is discarded here, so ``RICE``, ``Rice`` and ``rice`` are all
    the same description.
    """
    value = (value or '').strip().lower()
    value = value.replace('*', ' x ').replace('&', ' and ')
    value = re.sub(r'[^a-z0-9]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def _similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _product_descriptions(product):
    """Every catalogue string worth comparing an invoice description against."""
    return [t for t in (product.name, product.description) if t]


class CatalogueIndex:
    """Lookup tables over the active catalogue.

    Built once per upload: with ~5,000 products, comparing every invoice line
    against every product would mean hundreds of thousands of similarity
    computations, so exact lookups are hashed and the fuzzy pass is limited to
    candidates that share a word with the line.
    """

    def __init__(self, products=None):
        if products is None:
            products = Product.objects.filter(is_active=True)
        self.products = list(products)
        self.by_sku = {}
        self.by_barcode = {}
        self.by_text = defaultdict(list)
        self.by_token = defaultdict(list)

        for product in self.products:
            self.by_sku.setdefault(product.sku.strip().lower(), product)
            if product.barcode.strip():
                self.by_barcode.setdefault(product.barcode.strip().lower(), product)
            seen_text = set()
            for text in _product_descriptions(product):
                norm = normalise_text(text)
                if not norm or norm in seen_text:
                    continue
                seen_text.add(norm)
                self.by_text[norm].append(product)
            for token in set(normalise_text(product.name).split()):
                if len(token) >= 3:
                    self.by_token[token].append(product)

        # Sorted keys let prefix lookups run as a binary search.
        self.sorted_texts = sorted(self.by_text)

    def prefix_matches(self, norm_desc):
        """Products whose description begins with ``norm_desc`` at a word break.

        This is what lets the trailing part of a catalogue name be ignored:
        the invoice's "Greggs Black Pepper 12*100G" finds the catalogue's
        "Greggs Black Pepper 12*100G (516)".
        """
        if len(norm_desc) < MIN_PREFIX_CHARS:
            return []
        found = []
        i = bisect_left(self.sorted_texts, norm_desc)
        while i < len(self.sorted_texts):
            key = self.sorted_texts[i]
            if not key.startswith(norm_desc):
                break
            # Only break on a word boundary, so "rice" cannot swallow "ricemilk".
            if key == norm_desc or key.startswith(norm_desc + ' '):
                found.extend(self.by_text[key])
            i += 1
        return found

    def candidates(self, norm_desc):
        """Products sharing at least one word with the description, best first."""
        tokens = [t for t in set(norm_desc.split()) if len(t) >= 3]
        if not tokens:
            return self.products[:MAX_FUZZY_CANDIDATES]
        overlap = defaultdict(int)
        for token in tokens:
            for product in self.by_token.get(token, ()):
                overlap[product.pk] += 1
        if not overlap:
            return []
        by_pk = {p.pk: p for p in self.products}
        ranked = sorted(overlap.items(), key=lambda kv: -kv[1])[:MAX_FUZZY_CANDIDATES]
        return [by_pk[pk] for pk in (pk for pk, _ in ranked) if pk in by_pk]


def _describe_product(product):
    return {
        'catalogue_sku': product.sku,
        'catalogue_name': product.name,
        'catalogue_unit': product.unit,
        'catalogue_price': str(product.unit_price),
    }


def _unmatched_result(sku, description):
    return {
        'matched': False,
        'product_id': None,
        'match_type': None,
        'match_score': 0,
        'ambiguous': False,
        'field_matches': {
            'sku': 'unknown' if not sku else 'differs',
            'description': 'unknown' if not description else 'differs',
            'unit': 'unknown',
        },
        'warnings': ['No catalogue product matches this SKU or description.'],
        'notes': [],
        'catalogue_sku': '',
        'catalogue_name': '',
        'catalogue_unit': '',
        'catalogue_price': '',
    }


def compare_item(item, index=None, products=None):
    """Compare one extracted invoice line against the product catalogue.

    ``item`` is the dict produced by the PDF parser (``sku``, ``description``,
    ``unit``, …). Returns a dict of match fields to merge into that item:

        matched         — True when a catalogue product was found
        product_id      — pk of the matched product (or None)
        match_type      — 'sku' | 'barcode' | 'description' | 'similar' | None
        match_score     — 0-100, how confident the match is
        ambiguous       — several products fit the description and unit equally
        field_matches   — per field: 'match' | 'close' | 'differs' |
                          'unrecorded' | 'unknown'
        warnings        — things the user should check before dispatching
        notes           — informational remarks that are not problems
        catalogue_*     — the catalogue values, for side-by-side display
    """
    if index is None:
        index = CatalogueIndex(products)

    sku = (item.get('sku') or '').strip()
    description = (item.get('description') or '').strip()
    unit = (item.get('unit') or '').strip()

    norm_desc = normalise_text(description)

    product = None
    match_type = None
    ambiguous = False

    # 1. SKU is authoritative when it actually exists in the catalogue.
    if sku:
        product = index.by_sku.get(sku.lower())
        if product:
            match_type = 'sku'
        else:
            product = index.by_barcode.get(sku.lower())
            if product:
                match_type = 'barcode'

    # 2. Exact description match. Several products often share a description,
    #    so the unit decides between them.
    if product is None and norm_desc:
        exact = index.by_text.get(norm_desc) or []
        if exact:
            product, ambiguous = _pick_by_unit(exact, unit)
            match_type = 'description'

    # 3. The invoice description as a whole-word prefix of the catalogue one —
    #    the trailing catalogue text (a pack code, "(EXPORT)", …) is ignored.
    #    Prefer the product that adds the least on the end.
    if product is None and norm_desc:
        prefixed = index.prefix_matches(norm_desc)
        if prefixed:
            shortest = min(len(normalise_text(p.name)) for p in prefixed)
            closest = [p for p in prefixed if len(normalise_text(p.name)) == shortest]
            product, ambiguous = _pick_by_unit(closest, unit)
            match_type = 'prefix'

    # 4. Otherwise the closest description above the threshold, again with the
    #    unit breaking near-ties.
    if product is None and norm_desc:
        scored = []
        for candidate in index.candidates(norm_desc):
            score = max((_similarity(norm_desc, normalise_text(t))
                         for t in _product_descriptions(candidate)), default=0.0)
            if score >= FUZZY_THRESHOLD:
                scored.append((score, candidate))
        if scored:
            best_score = max(s for s, _ in scored)
            close = [c for s, c in scored if best_score - s <= 0.01]
            product, ambiguous = _pick_by_unit(close, unit)
            match_type = 'similar'

    if product is None:
        return _unmatched_result(sku, description)

    field_matches, warnings, notes, score = _compare_fields(
        product, sku, description, norm_desc, unit)

    if ambiguous:
        warnings.append(
            'Several catalogue products share this description and unit — '
            'confirm the right one before dispatching.')

    result = {
        'matched': True,
        'product_id': product.pk,
        'match_type': match_type,
        'match_score': score,
        'ambiguous': ambiguous,
        'field_matches': field_matches,
        'warnings': warnings,
        'notes': notes,
    }
    result.update(_describe_product(product))
    return result


def _pick_by_unit(candidates, unit):
    """Choose among same-description products using the unit.

    Returns (product, ambiguous). Ambiguous means the unit did not narrow the
    candidates down to one, so the caller should ask the user to confirm.
    """
    if len(candidates) == 1:
        return candidates[0], False
    exact = [p for p in candidates if compare_units(unit, p.unit) == 'match']
    if len(exact) == 1:
        return exact[0], False
    if exact:
        return exact[0], True
    close = [p for p in candidates if compare_units(unit, p.unit) == 'close']
    if len(close) == 1:
        return close[0], False
    return (close or candidates)[0], True


def _ignored_suffix(product, norm_desc):
    """The trailing catalogue text dropped when the invoice matched as a prefix.

    Returns the ignored words from the original (un-normalised) catalogue name,
    or None when the invoice description is not a whole-word prefix of it.
    """
    if len(norm_desc) < MIN_PREFIX_CHARS:
        return None
    for text in _product_descriptions(product):
        if not normalise_text(text).startswith(norm_desc + ' '):
            continue
        # Normalising can change the word count ("12*100G" becomes "12 x 100g"),
        # so find the split point in the original text rather than assuming it.
        words = text.split()
        for k in range(1, len(words)):
            if normalise_text(' '.join(words[:k])) == norm_desc:
                return ' '.join(words[k:])
        return text  # Prefix sits mid-word; report the whole catalogue name.
    return None


def _compare_fields(product, sku, description, norm_desc, unit):
    """Score the SKU / description / unit of a line against the matched product."""
    field_matches = {}
    warnings = []
    notes = []
    score = 0

    # ── SKU ──
    if not sku:
        field_matches['sku'] = 'unknown'
    elif product.sku.strip().lower() == sku.lower():
        field_matches['sku'] = 'match'
        score += 15
    elif product.barcode.strip() and product.barcode.strip().lower() == sku.lower():
        field_matches['sku'] = 'close'
        score += 12
        notes.append(f'Invoice SKU {sku} matched the barcode of {product.sku}.')
    elif looks_like_invoice_sku(sku) and not looks_like_invoice_sku(product.sku):
        # The catalogue stores name slugs, not Ah Liki supplier codes, so there
        # is nothing here to disagree with — this is not a mismatch.
        field_matches['sku'] = 'unrecorded'
        score += 8
        notes.append(
            f'No Ah Liki code is recorded in the catalogue for this product — '
            f'matched on description and unit instead.')
    else:
        field_matches['sku'] = 'differs'
        warnings.append(f'SKU differs — invoice "{sku}" vs catalogue "{product.sku}".')

    # ── Description (case-insensitive) ──
    if not description:
        field_matches['description'] = 'unknown'
    else:
        best = max((_similarity(norm_desc, normalise_text(t))
                    for t in _product_descriptions(product)), default=0.0)
        ignored = _ignored_suffix(product, norm_desc)
        if best >= 0.99:
            field_matches['description'] = 'match'
            score += 55
        elif ignored is not None:
            # The invoice description matches in full; the catalogue just adds
            # something on the end, which the user has asked us to ignore.
            field_matches['description'] = 'match'
            score += 55
            notes.append(f'Ignored trailing catalogue text "{ignored}" — the '
                         f'description matches up to that point.')
        elif best >= FUZZY_THRESHOLD:
            field_matches['description'] = 'close'
            score += 38
            warnings.append(
                f'Description is close but not identical — invoice "{description}" '
                f'vs catalogue "{product.name}".')
        else:
            field_matches['description'] = 'differs'
            warnings.append(
                f'Description differs — invoice "{description}" '
                f'vs catalogue "{product.name}".')

    # ── Unit ──
    verdict = compare_units(unit, product.unit)
    field_matches['unit'] = verdict
    if verdict == 'match':
        score += 30
    elif verdict == 'close':
        score += 15
        warnings.append(
            f'Pack size differs — invoice "{unit}" vs catalogue "{product.unit}". '
            'Check the quantity before dispatching.')
    elif verdict == 'unknown':
        score += 15
    else:
        warnings.append(
            f'Unit differs — invoice "{unit}" vs catalogue "{product.unit}". '
            'Check the quantity before dispatching.')

    return field_matches, warnings, notes, min(score, 100)


def annotate_items(items):
    """Compare every extracted line against the catalogue, in place."""
    index = CatalogueIndex()
    for item in items:
        item.update(compare_item(item, index=index))
    return items
