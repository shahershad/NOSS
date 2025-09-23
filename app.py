# app.py — Streamlit UI (global count mode + optional verb-before-keyword scoring)
import re
import html
from collections import Counter, defaultdict
import streamlit as st

from core.parser import parse_single_html
from core.keywords import GREEN_BASE_SET, IR_BASE_SET
from core.scoring import (
    build_regex_and_maps,            # keyword regex + maps (also merges custom keywords)
    default_weights, default_thresholds, default_count_mode,
    find_and_count_variants,         # used for non-verb aggregates
    compute_field_scores_dynamic,
    count_keywords_with_optional_verbs,
)
from core.pdf_builder import build_pdf_for_single
from ui.html_blocks import render_cu_block, inject_highlights
from ui.keywords_tab import render_keywords_tab
from core.verbs import build_verb_regex   # verbs in their own module

st.set_page_config(page_title="CU Analyzer (Single HTML → PDF)", layout="wide")

# ---------- Session settings ----------
if "weights" not in st.session_state:
    st.session_state.weights = default_weights.copy()
if "thresholds" not in st.session_state:
    st.session_state.thresholds = default_thresholds.copy()
# Global counting mode
if "count_mode" not in st.session_state:
    st.session_state.count_mode = default_count_mode  # "different" or "repeated"
# Global verb gating toggle
if "use_verbs" not in st.session_state:
    st.session_state.use_verbs = False

# Manual-entry state
if "manual_profile" not in st.session_state:
    st.session_state.manual_profile = {
        "SECTION": "", "GROUP": "", "AREA": "",
        "NOSS CODE": "", "NOSS TITLE": "", "NOSS LEVEL": ""
    }
if "manual_cus" not in st.session_state:
    # list of dicts: {"code":"","title":"","desc":"","wa":[],"pc":[]}
    st.session_state.manual_cus = []

# Build regex/maps once per run
VARIANTS_REGEX, VARIANT_TO_BASE, GREEN_BASE_SET_S, IR_BASE_SET_S = build_regex_and_maps()
VERBS_REGEX = build_verb_regex()  # compiled verb regex

st.title("📄 CU Analyzer — Single HTML → PDF")
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1) Analyze & Export",
    "2) Scoring Settings",
    "3) IR Keywords Browser",
    "4) Green Keywords Browser",
    "5) Manual Entry"
])

# ----------------- helpers for web highlighting ----------------- #
def _esc(s: str) -> str:
    return html.escape(s, quote=False)

def _split_sentences(text: str):
    if not text: return []
    return [p for p in re.split(r'(?<=[\.\!\?\:;])\s+|\n+', text) if p]

def highlight_text_web(text: str, *, use_verbs: bool):
    """
    Returns HTML string:
      - If use_verbs=False: keywords highlighted only (yellow/green)
      - If use_verbs=True : whole qualifying sentences blue; verbs red (ONLY inside those sentences); keywords yellow/green
    """
    if not text:
        return ""

    # NEW: collapse any hard newlines from pasted content into spaces so it stays a paragraph
    text = re.sub(r'[\r\n]+', ' ', text)

    if not use_verbs:
        matches = []
        tlow = text.lower()
        for m in VARIANTS_REGEX.finditer(tlow):
            base = VARIANT_TO_BASE.get(m.group(0).lower())
            if not base:
                continue
            cls = "hl-gt" if base in GREEN_BASE_SET_S else ("hl-ir" if base in IR_BASE_SET_S else None)
            if cls:
                matches.append((m.start(), m.end(), cls))
        return inject_highlights(text, matches)

    # verb-aware sentence highlighting
    parts = _split_sentences(text)

    def paint_sentence(sent: str):
        slow = sent.lower()
        verb_spans = [(m.start(), m.end()) for m in VERBS_REGEX.finditer(slow)]
        kw_spans = []
        for km in VARIANTS_REGEX.finditer(slow):
            base = VARIANT_TO_BASE.get(km.group(0).lower())
            if not base:
                continue
            cls = "hl-gt" if base in GREEN_BASE_SET_S else ("hl-ir" if base in IR_BASE_SET_S else None)
            if cls:
                kw_spans.append((km.start(), km.end(), cls))

        # qualifies if any verb occurs before any keyword
        qualifies = any(any(va < ka for (va, _vb) in verb_spans) for (ka, _kb, _) in kw_spans)

        # Build inner markup:
        # - always include keywords
        # - include verbs ONLY if qualifies
        spans = []
        if qualifies:
            spans += [("verb", a, b, None) for (a, b) in verb_spans]
        spans += [("kw", a, b, c) for (a, b, c) in kw_spans]
        spans.sort(key=lambda x: x[1])

        out, last = [], 0
        for typ, a, b, cls in spans:
            out.append(_esc(sent[last:a]))
            chunk = _esc(sent[a:b])
            if typ == "verb":  # only present when qualifies=True
                out.append(f'<span class="hl-verb">{chunk}</span>')
            else:
                out.append(f'<span class="{cls}">{chunk}</span>')
            last = b
        out.append(_esc(sent[last:]))

        joined = "".join(out)
        if qualifies:
            return f'<span class="hl-sent">{joined}</span>'
        return joined

    return " ".join(paint_sentence(p) for p in parts)


# ============================================================
#                      TAB 1: Analyze & Export
# ============================================================
with tab1:
    st.subheader("Upload a single NOSS HTML file, preview & export PDF")

    uploaded = st.file_uploader("Upload HTML file", type=["html", "htm"])
    if uploaded is not None:
        html_bytes = uploaded.read()
        profile_data, cu_blocks = parse_single_html(html_bytes)

        # ---- settings ----
        W = st.session_state.get("weights", default_weights)
        T = st.session_state.get("thresholds", default_thresholds)
        MODE = st.session_state.get("count_mode", default_count_mode)
        USE_VERBS = st.session_state.get("use_verbs", False)

        # ---- compute scores first (for summary) ----
        summary_rows = []
        gt_ge50 = ir_ge50 = 0
        per_cu_cache = []  # (cu, gt_scores, ir_scores, total_gt, total_ir)

        for cu in cu_blocks:
            gt_scores, ir_scores = compute_field_scores_dynamic(
                cu, W, T, MODE,
                VARIANTS_REGEX, VARIANT_TO_BASE,
                GREEN_BASE_SET_S, IR_BASE_SET_S,
                use_verbs=USE_VERBS, verbs_regex=VERBS_REGEX
            )
            total_gt = sum(gt_scores.values())
            total_ir = sum(ir_scores.values())
            summary_rows.append((cu.get("CU CODE",""), total_gt, total_ir))
            if total_gt >= 50: gt_ge50 += 1
            if total_ir >= 50: ir_ge50 += 1
            per_cu_cache.append((cu, gt_scores, ir_scores, total_gt, total_ir))

        # ---- profile ----
        st.markdown("### NOSS Profile")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**SECTION:** {profile_data.get('SECTION','')}")
            st.markdown(f"**GROUP:** {profile_data.get('GROUP','')}")
        with c2:
            st.markdown(f"**AREA:** {profile_data.get('AREA','')}")
            st.markdown(f"**NOSS CODE:** {profile_data.get('NOSS CODE','')}")
        with c3:
            st.markdown(f"**NOSS TITLE:** {profile_data.get('NOSS TITLE','')}")
            st.markdown(f"**NOSS LEVEL:** {profile_data.get('NOSS LEVEL','')}")

        # ---- summary of CU matching ----
        st.markdown("### Summary of CU Matching")
        if summary_rows:
            st.table({
                "CU": [f"CU {i+1}" for i in range(len(summary_rows))],
                "Green Technology": [f"{gt}%" for (_, gt, _) in summary_rows],
                "Industrial Revolution": [f"{ir}%" for (_, _, ir) in summary_rows],
            })
        else:
            st.info("No CU blocks found.")

        # ---- document-level share + Category outside the box ----
        total_cus = len(summary_rows)
        pct_gt = (gt_ge50/total_cus*100.0) if total_cus else 0.0
        pct_ir = (ir_ge50/total_cus*100.0) if total_cus else 0.0
        if pct_gt >= 50 and pct_ir >= 50:
            final_category = "IR4.0 + GREEN TECHNOLOGY"
        elif pct_gt >= 50:
            final_category = "GREEN TECHNOLOGY"
        elif pct_ir >= 50:
            final_category = "IR4.0"
        else:
            final_category = "MATCHED LESS 50%" if (gt_ge50 or ir_ge50) else "UNMATCHED"

        st.markdown("### Document-level Share of CUs ≥ 50%")
        st.table({
            "Metric":   ["IR ≥ 50% CU", "GT ≥ 50% CU"],
            "Value":    [ir_ge50, gt_ge50],
            "Total CU": [total_cus, total_cus],
            "Percent":  [f"{pct_ir:.0f}%", f"{pct_gt:.0f}%"],
        })
        st.markdown(f"**Category (new method):** {final_category}")
        if USE_VERBS:
            st.caption("Scoring mode: Verb required before keyword (same sentence).")

        # ---- Matched Keywords (document-level) ----
        file_base_gt = Counter()
        file_base_ir = Counter()
        var_examples_gt = defaultdict(Counter)
        var_examples_ir = defaultdict(Counter)

        for cu in cu_blocks:
            for field in ["CU TITLE", "CU DESCRIPTOR", "WORK ACTIVITY", "PERFORMANCE CRITERIA"]:
                text = (cu.get(field, "") or "")
                if USE_VERBS:
                    counts_by_base = count_keywords_with_optional_verbs(
                        text, VARIANTS_REGEX, VARIANT_TO_BASE, True, VERBS_REGEX
                    )
                    for sent in _split_sentences(text):
                        slow = sent.lower()
                        verb_spans = [(m.start(), m.end()) for m in VERBS_REGEX.finditer(slow)]
                        if not verb_spans:
                            continue
                        kw_iter = list(VARIANTS_REGEX.finditer(slow))
                        if not any(any(va < km.start() for (va, vb) in verb_spans) for km in kw_iter):
                            continue
                        for km in kw_iter:
                            base = VARIANT_TO_BASE.get(km.group(0).lower())
                            if not base: continue
                            if base in counts_by_base:
                                if base in GREEN_BASE_SET_S:
                                    file_base_gt[base] += 1
                                    var_examples_gt[base][km.group(0).lower()] += 1
                                if base in IR_BASE_SET_S:
                                    file_base_ir[base] += 1
                                    var_examples_ir[base][km.group(0).lower()] += 1
                else:
                    counts_by_base, matches = find_and_count_variants(text, VARIANTS_REGEX, VARIANT_TO_BASE)
                    for base, c in counts_by_base.items():
                        if base in GREEN_BASE_SET_S: file_base_gt[base] += c
                        if base in IR_BASE_SET_S:    file_base_ir[base] += c
                    for _, _, base, surface in matches:
                        if base in GREEN_BASE_SET_S: var_examples_gt[base][surface] += 1
                        if base in IR_BASE_SET_S:    var_examples_ir[base][surface] += 1

        def variant_examples_row(counter_map, base):
            if base not in counter_map or not counter_map[base]:
                return "—"
            items = counter_map[base].most_common(6)
            return "; ".join([f"{surf}×{cnt}" for surf, cnt in items])

        st.markdown("### Matched Keywords — Industrial Revolution")
        ir_rows = sorted(file_base_ir.items(), key=lambda x: (-x[1], x[0]))
        if ir_rows:
            st.table({
                "Keywords": [b for b,_ in ir_rows],
                "Variants": [variant_examples_row(var_examples_ir, b) for b,_ in ir_rows],
                "Amount":   [v for _,v in ir_rows],
            })
        else:
            st.info("No IR matches.")

        st.markdown("### Matched Keywords — Green Technology")
        gt_rows = sorted(file_base_gt.items(), key=lambda x: (-x[1], x[0]))
        if gt_rows:
            st.table({
                "Keywords": [b for b,_ in gt_rows],
                "Variants": [variant_examples_row(var_examples_gt, b) for b,_ in gt_rows],
                "Amount":   [v for _,v in gt_rows],
            })
        else:
            st.info("No GT matches.")

        # ---- PDF build ----
        pdf_bytes = build_pdf_for_single(
            profile_data, cu_blocks,
            weights=W, thresholds=T, count_mode=MODE,
            variants_regex=VARIANTS_REGEX,
            variant_to_base=VARIANT_TO_BASE,
            green_bases=GREEN_BASE_SET_S,
            ir_bases=IR_BASE_SET_S,
            final_category=final_category,
            use_verbs=USE_VERBS, verbs_regex=VERBS_REGEX
        )
        noss_code = profile_data.get("NOSS CODE","") or "document"
        safe_name = "".join([c if c.isalnum() or c in " _-" else "_" for c in noss_code]).strip() or "document"
        st.download_button("⬇️ Download PDF", data=pdf_bytes, file_name=f"{safe_name}.pdf", mime="application/pdf")

        # ---- CU details (inline HTML) ----
        st.markdown("### CU Details")
        st.caption("Yellow = Green Tech (GT), Green = Industrial Revolution (IR). Blue sentence = verb-before-keyword; verb is red.")

        for idx, (cu, gt_scores, ir_scores, total_gt, total_ir) in enumerate(per_cu_cache, 1):
            cu_code = cu.get("CU CODE","")

            cu_title_html = highlight_text_web(cu.get("CU TITLE",""), use_verbs=USE_VERBS)
            cu_desc_html  = highlight_text_web(cu.get("CU DESCRIPTOR",""), use_verbs=USE_VERBS)

            wa_raw = [pt.strip() for pt in (cu.get("WORK ACTIVITY","") or "").split(" - ") if pt.strip()] or [""]
            pc_raw = [pt.strip() for pt in (cu.get("PERFORMANCE CRITERIA","") or "").split(" - ") if pt.strip()] or [""]

            wa_items_html = [highlight_text_web(x, use_verbs=USE_VERBS) for x in wa_raw]
            pc_items_html = [highlight_text_web(x, use_verbs=USE_VERBS) for x in pc_raw]

            st.markdown(f"#### CU {idx}")
            html_block = render_cu_block(
                cu_code, cu_title_html, cu_desc_html,
                wa_items_html, pc_items_html,
                gt_scores, ir_scores, total_gt, total_ir
            )
            st.markdown(html_block, unsafe_allow_html=True)

    else:
        st.caption("Upload a NOSS HTML file to begin.")

# ============================================================
#                      TAB 2: Scoring Settings
# ============================================================
with tab2:
    st.subheader("Dynamic Scoring & Thresholds")

    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Weights**")
        w_title = st.number_input("CU TITLE weight", min_value=0, max_value=100, value=st.session_state.weights["CU TITLE"])
        w_desc  = st.number_input("CU DESCRIPTOR weight", min_value=0, max_value=100, value=st.session_state.weights["CU DESCRIPTOR"])
        w_wa    = st.number_input("WORK ACTIVITIES weight", min_value=0, max_value=100, value=st.session_state.weights["WORK ACTIVITY"])
        w_pc    = st.number_input("PERFORMANCE CRITERIA weight", min_value=0, max_value=100, value=st.session_state.weights["PERFORMANCE CRITERIA"])
    with colB:
        st.markdown("**Thresholds (full mark when reached)**")
        th_title = st.number_input("CU TITLE threshold", min_value=1, max_value=50, value=st.session_state.thresholds["CU TITLE"])
        th_desc  = st.number_input("CU DESCRIPTOR threshold", min_value=1, max_value=50, value=st.session_state.thresholds["CU DESCRIPTOR"])
        th_wa    = st.number_input("WORK ACTIVITIES threshold", min_value=1, max_value=200, value=st.session_state.thresholds["WORK ACTIVITY"])
        th_pc    = st.number_input("PERFORMANCE CRITERIA threshold", min_value=1, max_value=200, value=st.session_state.thresholds["PERFORMANCE CRITERIA"])

    st.markdown("**Counting mode (applies to ALL fields)**")
    mode_global = st.radio(
        "How should we count toward the thresholds?",
        ["Different (distinct keywords)", "Repeated (total occurrences)"],
        horizontal=True,
        index=0 if st.session_state.count_mode == "different" else 1
    )

    st.markdown("**Verb gating**")
    use_verbs_ui = st.checkbox("Require verb before keyword (same sentence) for scoring & blue sentence highlight",
                               value=st.session_state.use_verbs)

    if st.button("Apply settings"):
        st.session_state.weights = {
            "CU TITLE": int(w_title),
            "CU DESCRIPTOR": int(w_desc),
            "WORK ACTIVITY": int(w_wa),
            "PERFORMANCE CRITERIA": int(w_pc),
        }
        st.session_state.thresholds = {
            "CU TITLE": int(th_title),
            "CU DESCRIPTOR": int(th_desc),
            "WORK ACTIVITY": int(th_wa),
            "PERFORMANCE CRITERIA": int(th_pc),
        }
        st.session_state.count_mode = (
            "different" if mode_global.lower().startswith("different") else "repeated"
        )
        st.session_state.use_verbs = bool(use_verbs_ui)
        st.success("Settings updated.")

# ============================================================
#                      TAB 3: IR Keywords Browser
# ============================================================
with tab3:
    render_keywords_tab(
        tab_title="Industrial Revolution Base Keywords",
        default_bases=IR_BASE_SET,
        state_prefix="ir"
    )
# ============================================================
#                      TAB 4: Green Keywords Browser
# ============================================================
with tab4:
    render_keywords_tab(
        tab_title="Green Technology Base Keywords",
        default_bases=GREEN_BASE_SET,
        state_prefix="gt"
    )

# ============================================================
#                      TAB 5: Manual Entry
# ============================================================
with tab5:
    st.subheader("📋 Manual NOSS Entry Form")

    # ---------- Profile ----------
    st.markdown("### NOSS PROFILE")
    mp = st.session_state.manual_profile
    mp["SECTION"]   = st.text_input("SECTION", mp["SECTION"], key="mp_SECTION", placeholder="e.g., Manufacturing")
    mp["GROUP"]     = st.text_input("GROUP", mp["GROUP"], key="mp_GROUP")
    mp["AREA"]      = st.text_input("AREA", mp["AREA"], key="mp_AREA")
    mp["NOSS CODE"] = st.text_input("NOSS CODE", mp["NOSS CODE"], key="mp_CODE")
    mp["NOSS TITLE"]= st.text_input("NOSS TITLE", mp["NOSS TITLE"], key="mp_TITLE")
    mp["NOSS LEVEL"]= st.text_input("NOSS LEVEL", mp["NOSS LEVEL"], key="mp_LEVEL")

    st.markdown("---")
    st.markdown("### CU Entries")

    # add CU button
    if st.button("➕ Add New CU", key="add_cu_btn"):
        st.session_state.manual_cus.append({"code":"", "title":"", "desc":"", "wa":[], "pc":[]})
        st.rerun()

    # render each CU
    for i, cu in enumerate(st.session_state.manual_cus):
        st.markdown(f"#### CU {i+1}")

        cols_del = st.columns([0.9, 0.1])
        with cols_del[1]:
            if st.button("🗑️", key=f"del_cu_{i}", help="Delete this CU"):
                st.session_state.manual_cus.pop(i)
                st.rerun()

        cu["code"] = st.text_input(f"CU CODE {i+1}", cu.get("code",""), key=f"cu_{i}_code")
        cu["title"] = st.text_input(f"CU TITLE {i+1}", cu.get("title",""), key=f"cu_{i}_title")
        cu["desc"] = st.text_area(f"CU DESCRIPTOR {i+1}", cu.get("desc",""), key=f"cu_{i}_desc", height=120)

        st.markdown("**Work Activities & Performance Criteria**")

        n_pairs = max(len(cu["wa"]), len(cu["pc"]))
        j = 0
        while j < n_pairs:
            if j >= len(cu["wa"]): cu["wa"].append("")
            if j >= len(cu["pc"]): cu["pc"].append("")
            c1, c2, c3 = st.columns([0.48, 0.48, 0.04])
            with c1:
                cu["wa"][j] = st.text_area(f"WA {i+1}-{j+1}", cu["wa"][j], key=f"cu_{i}_wa_{j}", height=90)
            with c2:
                cu["pc"][j] = st.text_area(f"PC {i+1}-{j+1}", cu["pc"][j], key=f"cu_{i}_pc_{j}", height=90)
            with c3:
                if st.button("✖️", key=f"del_pair_{i}_{j}", help="Remove this WA/PC pair"):
                    cu["wa"].pop(j)
                    cu["pc"].pop(j)
                    n_pairs -= 1
                    st.rerun()
            j += 1

        if st.button(f"➕ Add WA & PC to CU {i+1}", key=f"add_pair_{i}"):
            cu["wa"].append("")
            cu["pc"].append("")
            st.rerun()

        st.markdown("---")

    # ---------- Generate PDF from manual entries ----------
    if st.button("📄 Generate PDF & Report", key="manual_generate"):
        cu_blocks = []
        for cu in st.session_state.manual_cus:
            wa_joined = " - ".join([w for w in cu["wa"] if (w or "").strip()])
            pc_joined = " - ".join([p for p in cu["pc"] if (p or "").strip()])
            cu_blocks.append({
                "CU CODE": cu.get("code",""),
                "CU TITLE": cu.get("title",""),
                "CU DESCRIPTOR": cu.get("desc",""),
                "WORK ACTIVITY": wa_joined,
                "PERFORMANCE CRITERIA": pc_joined,
            })

        W = st.session_state.get("weights", default_weights)
        T = st.session_state.get("thresholds", default_thresholds)
        MODE = st.session_state.get("count_mode", default_count_mode)
        USE_VERBS = st.session_state.get("use_verbs", False)

        gt_ge50 = ir_ge50 = 0
        for cu in cu_blocks:
            gt_scores, ir_scores = compute_field_scores_dynamic(
                cu, W, T, MODE,
                VARIANTS_REGEX, VARIANT_TO_BASE,
                GREEN_BASE_SET_S, IR_BASE_SET_S,
                use_verbs=USE_VERBS, verbs_regex=VERBS_REGEX
            )
            if sum(gt_scores.values()) >= 50: gt_ge50 += 1
            if sum(ir_scores.values()) >= 50: ir_ge50 += 1

        total_cus = len(cu_blocks)
        pct_gt = (gt_ge50/total_cus*100.0) if total_cus else 0.0
        pct_ir = (ir_ge50/total_cus*100.0) if total_cus else 0.0
        if pct_gt >= 50 and pct_ir >= 50:
            final_category = "IR4.0 + GREEN TECHNOLOGY"
        elif pct_gt >= 50:
            final_category = "GREEN TECHNOLOGY"
        elif pct_ir >= 50:
            final_category = "IR4.0"
        else:
            final_category = "MATCHED LESS 50%" if (gt_ge50 or ir_ge50) else "UNMATCHED"

        pdf_bytes = build_pdf_for_single(
            st.session_state.manual_profile, cu_blocks,
            weights=W, thresholds=T, count_mode=MODE,
            variants_regex=VARIANTS_REGEX,
            variant_to_base=VARIANT_TO_BASE,
            green_bases=GREEN_BASE_SET_S,
            ir_bases=IR_BASE_SET_S,
            final_category=final_category,
            use_verbs=USE_VERBS, verbs_regex=VERBS_REGEX
        )
        noss_code = st.session_state.manual_profile.get("NOSS CODE","") or "manual_document"
        safe_name = "".join([c if c.isalnum() or c in " _-" else "_" for c in noss_code]).strip() or "manual_document"
        st.download_button("⬇️ Download PDF", data=pdf_bytes, file_name=f"{safe_name}.pdf", mime="application/pdf")
