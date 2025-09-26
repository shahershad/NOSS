# ui/html_blocks.py — clean CU preview tables + CSS (adds sentence/verb highlight classes)

CU_TABLE_CSS = """
<style>
.cu-wrap{font-family:Inter,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.cu-table{width:100%;border-collapse:collapse;table-layout:fixed}
.cu-table td{border:1px solid #bbb;padding:8px;vertical-align:top;word-wrap:break-word;white-space:normal}
.cu-th{width:18%;font-weight:600;background:#fafafa}
.cu-wide{width:70%}
.cu-n{width:6%;text-align:center}
.cu-muted{background:#f4f4f4}
.cu-head{background:#eef4ff;font-weight:700}
.hl-gt{background:#FFF59D}  /* Green Tech (yellow) */
.hl-ir{background:#C8E6C9}  /* IR4.0 (green) */
.hl-sent{background:#E3F2FD;display:inline} /* qualifying sentence (blue) */
.hl-verb{color:#C62828;font-weight:600;display:inline} /* verb (only inside blue sentences) */
</style>
"""

def render_cu_block(cu_code, cu_title_html, cu_desc_html,
                    wa_items_html, pc_items_html,
                    gt_scores, ir_scores, total_gt, total_ir) -> str:
    rows_wa = "".join(
        f"""<tr>
              <td class="cu-th">{'WORK<br/>ACTIVITIES' if i==0 else ''}</td>
              <td class="cu-wide">• {txt}</td>
              <td class="cu-n">{str(gt_scores['WORK ACTIVITY'])+'%' if i==0 else ''}</td>
              <td class="cu-n">{str(ir_scores['WORK ACTIVITY'])+'%' if i==0 else ''}</td>
            </tr>"""
        for i, txt in enumerate(wa_items_html)
    )

    rows_pc = "".join(
        f"""<tr>
              <td class="cu-th">{'PERFORMANCE<br/>CRITERIA' if i==0 else ''}</td>
              <td class="cu-wide">• {txt}</td>
              <td class="cu-n">{str(gt_scores['PERFORMANCE CRITERIA'])+'%' if i==0 else ''}</td>
              <td class="cu-n">{str(ir_scores['PERFORMANCE CRITERIA'])+'%' if i==0 else ''}</td>
            </tr>"""
        for i, txt in enumerate(pc_items_html)
    )

    html = f"""
<div class="cu-wrap">
  <table class="cu-table">
    <tr class="cu-head">
      <td></td><td></td><td class="cu-n">GT</td><td class="cu-n">IR</td>
    </tr>
    <tr>
      <td class="cu-th">CU CODE</td>
      <td class="cu-wide">{cu_code}</td>
      <td class="cu-n"></td>
      <td class="cu-n"></td>
    </tr>
    <tr>
      <td class="cu-th">CU TITLE</td>
      <td class="cu-wide">{cu_title_html}</td>
      <td class="cu-n">{gt_scores['CU TITLE']}%</td>
      <td class="cu-n">{ir_scores['CU TITLE']}%</td>
    </tr>
    <tr>
      <td class="cu-th">CU DESCRIPTOR</td>
      <td class="cu-wide">{cu_desc_html}</td>
      <td class="cu-n">{gt_scores['CU DESCRIPTOR']}%</td>
      <td class="cu-n">{ir_scores['CU DESCRIPTOR']}%</td>
    </tr>
  </table>

  <table class="cu-table" style="margin-top:6px">
    <tr class="cu-head"><td></td><td></td><td class="cu-n">GT</td><td class="cu-n">IR</td></tr>
    {rows_wa}
  </table>

  <table class="cu-table" style="margin-top:6px">
    <tr class="cu-head"><td></td><td></td><td class="cu-n">GT</td><td class="cu-n">IR</td></tr>
    {rows_pc}
  </table>

  <table class="cu-table" style="margin-top:6px">
    <tr class="cu-head"><td></td><td></td><td class="cu-n">GT</td><td class="cu-n">IR</td></tr>
    <tr class="cu-muted">
      <td class="cu-th">TOTAL<br/>MATCH (%)</td>
      <td class="cu-wide"></td>
      <td class="cu-n">{total_gt}%</td>
      <td class="cu-n">{total_ir}%</td>
    </tr>
  </table>
</div>
"""
    return CU_TABLE_CSS + html

def inject_highlights(text: str, matches: list) -> str:
    """
    Wrap matched spans with <span class="hl-gt"> or <span class="hl-ir">.
    matches: [(start, end, class_name)]
    """
    if not text or not matches:
        return text or ""
    out, last = [], 0
    import html as _html
    for a, b, cls in matches:
        out.append(_html.escape(text[last:a]))
        out.append(f'<span class="{cls}">{_html.escape(text[a:b])}</span>')
        last = b
    out.append(_html.escape(text[last:]))
    return "".join(out)
