# core/scoring.py — keyword maps/regex + dynamic scoring
# Fixed to 'repeated' counting; verbs required ONLY for configured fields (e.g., WORK ACTIVITY).

import re
from collections import Counter
from core.keywords import (
    GREEN_BASE, IR_BASE, GREEN_BASE_SET, IR_BASE_SET,
    VARIANTS_GREEN_SEED, VARIANTS_IR_SEED,
    build_variant_map
)

# ---------------- Defaults ---------------- #
default_weights = {
    "CU TITLE": 5,
    "CU DESCRIPTOR": 20,
    "WORK ACTIVITY": 30,
    "PERFORMANCE CRITERIA": 45,
}

# thresholds = units needed for full mark.
# Units (this build):
# - For fields WITHOUT verb mode: total keyword hits (repeated).
# - For fields WITH verb mode   : total keyword hits but only inside qualifying items
#                                 (items where a verb appears before any keyword).
default_thresholds = {
    "CU TITLE": 1,
    "CU DESCRIPTOR": 3,
    "WORK ACTIVITY": 3,
    "PERFORMANCE CRITERIA": 3,
}


# ---------------- Regex builders ---------------- #
def build_regex_and_maps():
    """
    Build the master regex of all keyword variants and the map from surface->base.
    Uses ONLY explicit bases/variants (per core/keywords.py).
    """
    GREEN_BASE_SET_S, GREEN_V2B = build_variant_map(GREEN_BASE, VARIANTS_GREEN_SEED)
    IR_BASE_SET_S,    IR_V2B    = build_variant_map(IR_BASE,    VARIANTS_IR_SEED)

    variant_to_base = {}
    variant_to_base.update(GREEN_V2B)
    variant_to_base.update(IR_V2B)

    all_variants = sorted(variant_to_base.keys(), key=len, reverse=True)
    pat = "|".join(re.escape(v) for v in all_variants) if all_variants else r"(?!x)x"
    variants_regex = re.compile(rf"(?<!\w)(?:{pat})(?!\w)", re.IGNORECASE)
    return variants_regex, variant_to_base, GREEN_BASE_SET_S, IR_BASE_SET_S


# ---------------- Basic counting (no verbs) ---------------- #
def find_and_count_variants(text: str, variants_regex, variant_to_base):
    """
    Count all keyword occurrences in text (repeated counts).
    Returns (Counter by base, matches list).
    matches: [(start, end, base, surface)]
    """
    counts_by_base = Counter()
    matches = []
    if not text:
        return counts_by_base, matches
    tlow = text.lower()
    for m in variants_regex.finditer(tlow):
        surface = m.group(0).lower()
        base = variant_to_base.get(surface)
        if base:
            counts_by_base[base] += 1
            matches.append((m.start(), m.end(), base, surface))
    return counts_by_base, matches


# ---------------- Helpers for verb mode ---------------- #
# Sentence splitter used for aggregates (also splits on " - " joiner)
_SENT_SPLIT = re.compile(r'(?<=[\.\!\?\:;])\s+|\n+|\s-\s+')
# Item splitter for WA/PC fields (parser joins bullets using " - ")
_ITEM_SPLIT = re.compile(r'\s-\s+')

def _iter_field_items(field: str, text: str):
    """
    Yield independent items for scoring:
      - For WA/PC: split the field by " - "
      - For TITLE/DESCRIPTOR: the whole field is one item
    """
    text = (text or "").strip()
    if not text:
        return []
    if field in ("WORK ACTIVITY", "PERFORMANCE CRITERIA"):
        items = [p.strip() for p in _ITEM_SPLIT.split(text) if p.strip()]
        return items or [text]
    return [text]


def _count_verb_mode_units_for_field(field: str, text: str, *,
                                     variants_regex, variant_to_base, verbs_regex,
                                     green_bases, ir_bases):
    """
    Item-wise verb mode (repeated):
      - An item qualifies iff some verb occurs before any keyword in that item.
      - Units = total keyword hits inside qualifying items (GT/IR counted separately).
    Returns (gt_units, ir_units).
    """
    if not text:
        return 0, 0

    gt_units = 0
    ir_units = 0

    for item in _iter_field_items(field, text):
        s = item.lower()
        verbs = list(verbs_regex.finditer(s))
        kws   = list(variants_regex.finditer(s))
        if not kws or not verbs:
            continue

        qualifies = any(v.start() < k.start() for v in verbs for k in kws)
        if not qualifies:
            continue

        for km in kws:
            base = variant_to_base.get(km.group(0).lower())
            if not base:
                continue
            if base in green_bases:
                gt_units += 1
            if base in ir_bases:
                ir_units += 1

    return gt_units, ir_units


def count_keywords_with_optional_verbs(text: str,
                                       variants_regex, variant_to_base,
                                       require_verb_before: bool,
                                       verbs_regex):
    """
    Aggregate counts for the doc-level "Matched Keywords" tables.
    When require_verb_before=True, only count keyword hits that are inside
    qualifying items (splitting on punctuation and " - ").
    """
    counts = Counter()
    if not text:
        return counts

    parts = [p.strip().lower() for p in _SENT_SPLIT.split(text) if p.strip()]
    for s in parts:
        kw_iter = list(variants_regex.finditer(s))
        if not kw_iter:
            continue
        if require_verb_before:
            verbs = list(verbs_regex.finditer(s))
            if not verbs or not any(v.start() < k.start() for v in verbs for k in kw_iter):
                continue
        for km in kw_iter:
            base = variant_to_base.get(km.group(0).lower())
            if base:
                counts[base] += 1
    return counts


# ---------------- Scoring ---------------- #
def compute_field_scores_dynamic(cu, weights, thresholds,
                                 variants_regex, variant_to_base,
                                 green_bases, ir_bases,
                                 verbs_regex=None, verbs_required_fields=None):
    """
    Compute per-field GT/IR scores.
    - Fields listed in verbs_required_fields use verb mode (repeated inside qualifying items).
    - All other fields use repeated keyword counting over the whole field.
    Score = round(weight * min(units / threshold, 1.0))
    """
    verbs_required_fields = set(verbs_required_fields or [])

    gt_scores, ir_scores = {}, {}

    for field, w in weights.items():
        text = (cu.get(field, "") or "")
        th = max(1, thresholds.get(field, 1))

        if verbs_regex is not None and field in verbs_required_fields:
            gt_units, ir_units = _count_verb_mode_units_for_field(
                field, text,
                variants_regex=variants_regex,
                variant_to_base=variant_to_base,
                verbs_regex=verbs_regex,
                green_bases=green_bases,
                ir_bases=ir_bases,
            )
        else:
            counts_by_base, _ = find_and_count_variants(text, variants_regex, variant_to_base)
            gt_units = sum(c for b, c in counts_by_base.items() if b in green_bases)
            ir_units = sum(c for b, c in counts_by_base.items() if b in ir_bases)

        gt_scores[field] = int(round(w * min(gt_units / th, 1.0)))
        ir_scores[field] = int(round(ir_units / th * w if (ir_units / th) < 1.0 else w))

    return gt_scores, ir_scores
