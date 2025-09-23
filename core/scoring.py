# core/scoring.py — keyword/variant regex + scoring (global count mode + optional verb gating)
import re
from collections import Counter
from copy import deepcopy

from utils.file_persist import load as _kw_load
from core.keywords import (
    GREEN_BASE, IR_BASE,
    VARIANTS_GREEN_SEED, VARIANTS_IR_SEED,
    build_variant_map
)

# Field weights (sum to 100 by default)
default_weights = {
    "CU TITLE": 5,
    "CU DESCRIPTOR": 20,
    "WORK ACTIVITY": 30,
    "PERFORMANCE CRITERIA": 45,
}
# Thresholds (how many needed for full mark per field)
default_thresholds = {
    "CU TITLE": 1,
    "CU DESCRIPTOR": 3,
    "WORK ACTIVITY": 3,
    "PERFORMANCE CRITERIA": 3,
}
# Global counting mode for all fields:
#   "different" => distinct base keywords required
#   "repeated"  => total occurrences (repeats count)
default_count_mode = "different"

def _merge_custom_into(bases_list, seed_dict, prefix):
    data = _kw_load(prefix) or {}
    for _, obj in data.items():
        base_label = (obj.get("label") or "").strip()
        if not base_label:
            continue
        bases_list.append(base_label)
        variants = obj.get("variants") or []
        if variants:
            seed_dict.setdefault(base_label.lower(), []).extend([v.strip() for v in variants if v.strip()])

def build_regex_and_maps():
    """Compile regex for all keyword variants (default + user-added)."""
    green_bases = list(deepcopy(GREEN_BASE))
    ir_bases    = list(deepcopy(IR_BASE))
    green_seeds = deepcopy(VARIANTS_GREEN_SEED)
    ir_seeds    = deepcopy(VARIANTS_IR_SEED)

    _merge_custom_into(green_bases, green_seeds, "gt")
    _merge_custom_into(ir_bases,    ir_seeds,    "ir")

    GREEN_BASE_SET_S, GREEN_V2B = build_variant_map(green_bases, green_seeds)
    IR_BASE_SET_S,    IR_V2B    = build_variant_map(ir_bases,    ir_seeds)

    VARIANT_TO_BASE = {}
    VARIANT_TO_BASE.update(GREEN_V2B)
    VARIANT_TO_BASE.update(IR_V2B)

    ALL_VARIANTS = sorted(VARIANT_TO_BASE.keys(), key=len, reverse=True)
    pat = "|".join(re.escape(v) for v in ALL_VARIANTS) if ALL_VARIANTS else r"(?!x)x"
    VARIANTS_REGEX = re.compile(rf"(?<!\w)(?:{pat})(?!\w)", re.IGNORECASE)
    return VARIANTS_REGEX, VARIANT_TO_BASE, GREEN_BASE_SET_S, IR_BASE_SET_S

def find_and_count_variants(text: str, variants_regex, variant_to_base):
    """Simple (non-verb) counting helper used for document tables."""
    counts_by_base = Counter()
    matches = []
    if not text: return counts_by_base, matches
    tlow = text.lower()
    for m in variants_regex.finditer(tlow):
        surface = m.group(0).lower()
        base = variant_to_base.get(surface)
        if base:
            counts_by_base[base] += 1
            matches.append((m.start(), m.end(), base, surface))
    return counts_by_base, matches

# ---------------------- Verb-aware counting ---------------------- #
_SENT_SPLIT = re.compile(r'(?<=[\.\!\?\:;])\s+|\n+')

def split_sentences(text: str):
    if not text:
        return []
    parts = [p for p in _SENT_SPLIT.split(text) if p]
    return parts

def compile_verbs_regex(verb_phrases):
    phrases = sorted({v.strip().lower() for v in verb_phrases if v.strip()}, key=len, reverse=True)
    if not phrases:
        return re.compile(r"(?!x)x")
    pat = "|".join(re.escape(p) for p in phrases)
    return re.compile(rf"(?<!\w)(?:{pat})(?!\w)", re.IGNORECASE)

def count_keywords_with_optional_verbs(text: str,
                                       variants_regex, variant_to_base,
                                       require_verb_before: bool,
                                       verbs_regex=None):
    """
    Returns counts_by_base where (if require_verb_before) only keywords
    in a sentence WITH a verb appearing BEFORE the keyword are counted.
    """
    counts_by_base = Counter()
    if not text:
        return counts_by_base

    if not require_verb_before:
        counts_by_base, _ = find_and_count_variants(text, variants_regex, variant_to_base)
        return counts_by_base

    for sent in split_sentences(text):
        tlow = sent.lower()
        verb_spans = [ (m.start(), m.end()) for m in (verbs_regex.finditer(tlow) if verbs_regex else []) ]
        if not verb_spans:
            continue
        for m in variants_regex.finditer(tlow):
            a = m.start()
            surf = m.group(0).lower()
            if any(va < a for (va, vb) in verb_spans):
                base = variant_to_base.get(surf)
                if base:
                    counts_by_base[base] += 1
    return counts_by_base

# --------------------------- Scoring ---------------------------- #
def _score_value(count, threshold, weight):
    proportion = min(count / max(threshold, 1), 1.0)
    return int(round(weight * proportion))

def compute_field_scores_dynamic(cu, weights, thresholds, count_mode,
                                 variants_regex, variant_to_base,
                                 green_bases, ir_bases,
                                 use_verbs: bool = False, verbs_regex=None):
    """
    Scoring with user-configurable weights, thresholds, a GLOBAL counting mode,
    and optional verb gating (verb must be in the same sentence and BEFORE the keyword).
    """
    mode = (count_mode or "different").lower()
    gt_scores, ir_scores = {}, {}

    for field, w in weights.items():
        text = (cu.get(field, "") or "")

        if use_verbs:
            counts_by_base = count_keywords_with_optional_verbs(
                text, variants_regex, variant_to_base, True, verbs_regex
            )
        else:
            counts_by_base, _ = find_and_count_variants(text, variants_regex, variant_to_base)

        gt_bases_set = {b for b in counts_by_base if b in green_bases}
        ir_bases_set = {b for b in counts_by_base if b in ir_bases}

        if mode == "repeated":
            gt_count = sum(counts_by_base[b] for b in gt_bases_set)
            ir_count = sum(counts_by_base[b] for b in ir_bases_set)
        else:  # "different"
            gt_count = len(gt_bases_set)
            ir_count = len(ir_bases_set)

        th = thresholds.get(field, 1)
        gt_scores[field] = _score_value(gt_count, th, w)
        ir_scores[field] = _score_value(ir_count, th, w)

    return gt_scores, ir_scores
