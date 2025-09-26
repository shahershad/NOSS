# core/pdf_builder.py — build PDF (BytesIO) from parsed data with verb/sentence highlighting
import io
from collections import Counter, defaultdict
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, PageBreak, Table, TableStyle, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT

from core.scoring import (
    compute_field_scores_dynamic,
    count_keywords_with_optional_verbs,   # kept for completeness (not used in doc-level tables)
    find_and_count_variants,
)

# --- optional page numbers ---
def _numbered(canvas, doc):
    page_num = canvas.getPageNumber()
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {page_num}")

def _split_sentences_for_pdf(text):
    import re
    if not text:
        return []
    parts = re.split(r'(?<=[\.\!\?\:;])\s+|\n+', text)
    return [p for p in parts if p]

def _hilite_pdf_keywords_only(text, variants_regex, variant_to_base, green_bases, ir_bases):
    """Highlight only keywords (no verb/sentence logic). Safely escapes other text."""
    if not text:
        return ""
    import html as _html
    s = text
    tlow = s.lower()
    matches = []
    for m in variants_regex.finditer(tlow):
        surface = m.group(0).lower()
        base = variant_to_base.get(surface)
        if not base:
            continue
        color = "#FFF59D" if base in green_bases else ("#C8E6C9" if base in ir_bases else None)
        if color:
            matches.append((m.start(), m.end(), color))
    if not matches:
        return _html.escape(s, quote=False)
    out, last = [], 0
    for a, b, color in matches:
        out.append(_html.escape(s[last:a], quote=False))
        surf = _html.escape(s[a:b], quote=False)
        out.append(f'<font backcolor="{color}">{surf}</font>')
        last = b
    out.append(_html.escape(s[last:], quote=False))
    return "".join(out)

def _hilite_pdf_with_verbs(text, variants_regex, variant_to_base, verbs_regex,
                           green_bases, ir_bases):
    """
    Highlight whole qualifying sentences blue (#E3F2FD),
    verbs red (only inside qualifying sentences),
    and keywords in their GT/IR backcolors everywhere.
    A sentence qualifies if a verb appears before any keyword.
    """
    if not text:
        return ""

    def paint_sentence(sent: str):
        import html as _html
        tlow = sent.lower()

        # collect spans
        verb_spans = [(m.start(), m.end()) for m in verbs_regex.finditer(tlow)]
        kw_spans = []
        for m in variants_regex.finditer(tlow):
            surf = m.group(0).lower()
            base = variant_to_base.get(surf)
            if not base:
                continue
            bg = "#FFF59D" if base in green_bases else ("#C8E6C9" if base in ir_bases else None)
            if bg:
                kw_spans.append((m.start(), m.end(), bg))

        # sentence qualifies if any verb occurs before any keyword
        qualifies = any(any(va < ka for (va, vb) in verb_spans) for (ka, kb, _) in kw_spans)

        spans = []
        if qualifies:
            spans += [("verb", a, b, None) for (a, b) in verb_spans]
        spans += [("kw", a, b, c) for (a, b, c) in kw_spans]
        spans.sort(key=lambda x: x[1])

        out, last = [], 0
        for typ, a, b, color in spans:
            out.append(_html.escape(sent[last:a], quote=False))
            chunk = _html.escape(sent[a:b], quote=False)
            if typ == "verb":
                out.append(f'<font color="#C62828">{chunk}</font>')
            else:
                out.append(f'<font backcolor="{color}">{chunk}</font>')
            last = b
        out.append(_html.escape(sent[last:], quote=False))

        joined = "".join(out)
        if qualifies:
            return f'<font backcolor="#E3F2FD">{joined}</font>'
        return joined

    parts = _split_sentences_for_pdf(text)
    decorated = [paint_sentence(p) for p in parts]
    return " ".join(decorated)


def build_pdf_for_single(profile_data, cu_blocks, *,
                         weights, thresholds,
                         variants_regex, variant_to_base,
                         green_bases, ir_bases,
                         final_category,
                         verbs_regex=None, verbs_required_fields=None,
                         cu_pass_threshold=50, doc_share_threshold=50):
    styles = getSampleStyleSheet()
    styleN = styles['Normal']
    styleH = styles['Heading2']
    styleH.alignment = TA_LEFT  # ensure headings are left-aligned
    wrap_style = ParagraphStyle(name='WrapStyle', parent=styleN,
                                alignment=TA_JUSTIFY, spaceAfter=6)

    # Layout constants (use top-level cm import)
    left_margin = right_margin = top_margin = bottom_margin = 2 * cm
    avail_w = A4[0] - (left_margin + right_margin)

    # Helper to build a full-width, centered-cell table
    def fullwidth_centered_table(data, col_fracs, header_bg=None):
        col_widths = [avail_w * f for f in col_fracs]
        t = Table(data, colWidths=col_widths, hAlign="LEFT")
        base = [
            ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]
        if header_bg:
            base.append(('BACKGROUND', (0, 0), (-1, 0), header_bg))
        else:
            base.append(('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey))
        t.setStyle(TableStyle(base))
        return t

    # ---------- Header ----------
    flowables = []
    flowables.append(Paragraph("<b>NOSS PROFILE</b>", styleH))
    flowables.append(Spacer(1, 0.3 * cm))
    for label_text in ["SECTION", "GROUP", "AREA", "NOSS CODE", "NOSS TITLE", "NOSS LEVEL"]:
        flowables.append(Paragraph(f"<b>{label_text}:</b> {profile_data.get(label_text, '')}", styleN))
    flowables.append(Spacer(1, 0.4 * cm))

    # ---------- Per-CU scores + summary ----------
    summary_data = [["CU", "Green Technology", "Industrial Revolution"]]
    per_cu_scores = []
    for i, cu in enumerate(cu_blocks, 1):
        gt_scores, ir_scores = compute_field_scores_dynamic(
            cu, weights, thresholds,
            variants_regex, variant_to_base,
            green_bases, ir_bases,
            verbs_regex=verbs_regex, verbs_required_fields=verbs_required_fields
        )
        total_gt = sum(gt_scores.values())
        total_ir = sum(ir_scores.values())
        per_cu_scores.append((gt_scores, ir_scores, total_gt, total_ir))
        summary_data.append([f"CU {i}", f"{total_gt}%", f"{total_ir}%"])

    flowables.append(Paragraph("<b>Summary of CU Matching</b>", styleH))
    flowables.append(Spacer(1, 0.3 * cm))
    # 3 columns: 20% / 40% / 40%
    summary_table = fullwidth_centered_table(summary_data, [0.2, 0.4, 0.4])
    flowables.append(summary_table)
    flowables.append(Spacer(1, 0.4 * cm))

    # ---------- Document-level share ----------
    flowables.append(Paragraph(f"<b>Document-level Share of CUs ≥ {cu_pass_threshold}%</b>", styleH))
    flowables.append(Spacer(1, 0.2 * cm))
    total_cus = len(per_cu_scores)
    gt_geT   = sum(1 for (_, _, tg, ti) in per_cu_scores if tg >= cu_pass_threshold)
    ir_geT   = sum(1 for (_, _, tg, ti) in per_cu_scores if ti >= cu_pass_threshold)
    doc_rows = [
        ["Metric", "Value", "Total CU", "Percent"],
        [f"IR ≥ {cu_pass_threshold}% CU", str(ir_geT), str(total_cus), f"{(ir_geT/total_cus*100.0 if total_cus else 0):.0f}%"],
        [f"GT ≥ {cu_pass_threshold}% CU", str(gt_geT), str(total_cus), f"{(gt_geT/total_cus*100.0 if total_cus else 0):.0f}%"],
    ]
    # 4 columns: 40% / 20% / 20% / 20%
    doc_table = fullwidth_centered_table(doc_rows, [0.4, 0.2, 0.2, 0.2])
    flowables.append(doc_table)
    flowables.append(Spacer(1, 0.2 * cm))
    flowables.append(Paragraph(f"<b>Category (threshold {doc_share_threshold}%):</b> {final_category}", styleN))
    flowables.append(Spacer(1, 0.4 * cm))

    # ---------- Matched Keywords (document-level) ----------
    file_base_gt = Counter(); file_base_ir = Counter()
    var_examples_gt = defaultdict(Counter); var_examples_ir = defaultdict(Counter)

    for cu in cu_blocks:
        for field in ["CU TITLE", "CU DESCRIPTOR", "WORK ACTIVITY", "PERFORMANCE CRITERIA"]:
            text = (cu.get(field, "") or "")
            counts_by_base, matches = find_and_count_variants(text, variants_regex, variant_to_base)
            for base, c in counts_by_base.items():
                if base in green_bases: file_base_gt[base] += c
                if base in ir_bases:    file_base_ir[base] += c
            for _, _, base, surface in matches:
                if base in green_bases: var_examples_gt[base][surface] += 1
                if base in ir_bases:    var_examples_ir[base][surface] += 1

    def examples_str(counter_map, base):
        if base not in counter_map or not counter_map[base]:
            return "—"
        items = counter_map[base].most_common(6)
        return "; ".join([f"{s}×{c}" for s, c in items])

    # IR table
    flowables.append(Paragraph("<b>Matched Keywords — Industrial Revolution</b>", styleH))
    ir_list = sorted(file_base_ir.items(), key=lambda x: (-x[1], x[0])) or [("—", 0)]
    ir_rows = [["Keywords", "Variants", "Amount"]]
    for base, cnt in ir_list:
        ir_rows.append([base, examples_str(var_examples_ir, base), str(cnt)])
    ir_table = fullwidth_centered_table(ir_rows, [0.5, 0.4, 0.1], header_bg=colors.HexColor("#C8E6C9"))
    flowables.append(ir_table)
    flowables.append(Spacer(1, 0.3 * cm))

    # GT table
    flowables.append(Paragraph("<b>Matched Keywords — Green Technology</b>", styleH))
    gt_list = sorted(file_base_gt.items(), key=lambda x: (-x[1], x[0])) or [("—", 0)]
    gt_rows = [["Keywords", "Variants", "Amount"]]
    for base, cnt in gt_list:
        gt_rows.append([base, examples_str(var_examples_gt, base), str(cnt)])
    gt_table = fullwidth_centered_table(gt_rows, [0.5, 0.4, 0.1], header_bg=colors.HexColor("#FFF59D"))
    flowables.append(gt_table)
    flowables.append(Spacer(1, 0.4 * cm))

    # ---------- CU detail pages (each CU on a new page) ----------
    flowables.append(PageBreak())  # Start CU 1 on a fresh page

    for i, (cu, sc) in enumerate(zip(cu_blocks, per_cu_scores), 1):
        gt_scores, ir_scores, total_gt, total_ir = sc

        # TITLE / DESCRIPTOR (keyword-only)
        cu_title = _hilite_pdf_keywords_only(
            cu.get("CU TITLE", ""), variants_regex, variant_to_base, green_bases, ir_bases
        )
        cu_desc = _hilite_pdf_keywords_only(
            cu.get("CU DESCRIPTOR", ""), variants_regex, variant_to_base, green_bases, ir_bases
        )

        # WORK ACTIVITIES — split raw, then highlight (verbs required)
        wa_raw = [pt.strip() for pt in (cu.get("WORK ACTIVITY", "") or "").split(" - ") if pt.strip()] or [""]
        if verbs_regex:
            wa_items = [
                _hilite_pdf_with_verbs(pt, variants_regex, variant_to_base, verbs_regex, green_bases, ir_bases)
                for pt in wa_raw
            ]
        else:
            wa_items = [
                _hilite_pdf_keywords_only(pt, variants_regex, variant_to_base, green_bases, ir_bases)
                for pt in wa_raw
            ]

        # PERFORMANCE CRITERIA — split raw, then keyword highlight
        pc_raw = [pt.strip() for pt in (cu.get("PERFORMANCE CRITERIA", "") or "").split(" - ") if pt.strip()] or [""]
        pc_items = [
            _hilite_pdf_keywords_only(pt, variants_regex, variant_to_base, green_bases, ir_bases)
            for pt in pc_raw
        ]

        # ---------- Render CU ----------
        flowables.append(Paragraph(f"<b>CU {i}</b>", styleH))
        flowables.append(Spacer(1, 0.2 * cm))

        table1 = Table(
            [
                ["", "", "GT", "IR"],
                ["CU CODE", cu.get("CU CODE", ""), "", ""],
                ["CU TITLE", Paragraph(cu_title, wrap_style), f"{gt_scores['CU TITLE']}%", f"{ir_scores['CU TITLE']}%"],
                ["CU DESCRIPTOR", Paragraph(cu_desc, wrap_style), f"{gt_scores['CU DESCRIPTOR']}%", f"{ir_scores['CU DESCRIPTOR']}%"],
            ],
            colWidths=[3.5 * cm, avail_w - (2 * 1.25 * cm) - 3.5 * cm, 1.25 * cm, 1.25 * cm],
            hAlign="LEFT",
        )
        table1.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4ff")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (2, 0), (3, 0), "CENTER"),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.grey),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                ]
            )
        )
        flowables.append(table1)
        flowables.append(Spacer(1, 0.2 * cm))

        # WA table
        wa_data = [["", "", "GT", "IR"]]
        for j, pt in enumerate(wa_items):
            wa_data.append(
                [
                    Paragraph("WORK<br/>ACTIVITIES", wrap_style) if j == 0 else "",
                    Paragraph(f"• {pt}", wrap_style),
                    f"{gt_scores['WORK ACTIVITY']}%" if j == 0 else "",
                    f"{ir_scores['WORK ACTIVITY']}%" if j == 0 else "",
                ]
            )
        table2 = Table(
            wa_data,
            colWidths=[3.5 * cm, avail_w - (2 * 1.25 * cm) - 3.5 * cm, 1.25 * cm, 1.25 * cm],
            hAlign="LEFT",
        )
        table2.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4ff")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (2, 0), (3, 0), "CENTER"),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.grey),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                ]
            )
        )
        flowables.append(table2)
        flowables.append(Spacer(1, 0.2 * cm))

        # PC table
        pc_data = [["", "", "GT", "IR"]]
        for j, pt in enumerate(pc_items):
            pc_data.append(
                [
                    Paragraph("PERFORMANCE<br/>CRITERIA", wrap_style) if j == 0 else "",
                    Paragraph(f"• {pt}", wrap_style),
                    f"{gt_scores['PERFORMANCE CRITERIA']}%" if j == 0 else "",
                    f"{ir_scores['PERFORMANCE CRITERIA']}%" if j == 0 else "",
                ]
            )
        table3 = Table(
            pc_data,
            colWidths=[3.5 * cm, avail_w - (2 * 1.25 * cm) - 3.5 * cm, 1.25 * cm, 1.25 * cm],
            hAlign="LEFT",
        )
        table3.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4ff")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (2, 0), (3, 0), "CENTER"),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.grey),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                ]
            )
        )
        flowables.append(table3)
        flowables.append(Spacer(1, 0.2 * cm))

        # TOTAL
        total_table = Table(
            [
                ["", "", "GT", "IR"],
                [Paragraph("TOTAL<br/>MATCH (%)", wrap_style), "", f"{total_gt}%", f"{total_ir}%"],
            ],
            colWidths=[3.5 * cm, avail_w - (2 * 1.25 * cm) - 3.5 * cm, 1.25 * cm, 1.25 * cm],
            hAlign="LEFT",
        )
        total_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4ff")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (2, 0), (3, 0), "CENTER"),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.lightgrey),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ]
            )
        )
        flowables.append(total_table)

        if i < len(cu_blocks):
            flowables.append(PageBreak())

    # Build PDF in-memory
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
    )
    doc.build(flowables, onFirstPage=_numbered, onLaterPages=_numbered)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
