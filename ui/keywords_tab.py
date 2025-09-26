# ui/keywords_tab.py — Keywords management tab for Streamlit (unchanged)

from typing import Set, Dict, List
import streamlit as st
from utils.file_persist import load as file_load, save as file_save, clear as file_clear

LETTERS = [chr(i) for i in range(ord("A"), ord("Z") + 1)]

def _ensure_state(prefix: str) -> str:
    key = f"{prefix}_custom"
    if key not in st.session_state:
        st.session_state[key] = {}
    return key

def _norm(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()

def _split_variants(s: str) -> List[str]:
    if not s:
        return []
    parts = [p.strip() for p in s.replace(";", "\n").replace(",", "\n").split("\n")]
    out: List[str] = []
    seen = set()
    for p in parts:
        if not p:
            continue
        key = _norm(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p.strip())
    return out

def _filter_items(items: List[str], choice: str) -> List[str]:
    items = sorted(items, key=lambda x: x.lower())
    if choice == "Top 10":
        return items[:10]
    if choice == "All":
        return items
    return [w for w in items if w.lower().startswith(choice.lower())]

def _grid_render_bases(bases: List[str]) -> None:
    cols = st.columns(5)
    for i, kw in enumerate(bases):
        with cols[i % 5]:
            st.markdown(f"<div style='padding:4px 0'>{kw}</div>", unsafe_allow_html=True)

def _persist(prefix: str, state_key: str) -> None:
    try:
        file_save(prefix, st.session_state[state_key])
    except Exception as e:
        st.error(f"Failed to save keywords: {e}")

def render_keywords_tab(*, tab_title: str, default_bases: Set[str], state_prefix: str) -> None:
    st.subheader(tab_title)

    state_key = _ensure_state(state_prefix)
    boot_flag = f"{state_prefix}_bootstrapped_from_file"
    if not st.session_state.get(boot_flag):
        st.session_state[state_key] = file_load(state_prefix) or {}
        st.session_state[boot_flag] = True

    custom_dict: Dict[str, Dict[str, List[str]]] = st.session_state[state_key]

    col_sel, col_sp, col_reload, col_clear = st.columns([3, 1, 1, 2])
    with col_sel:
        choice = st.selectbox("Show", ["Top 10", "All", *LETTERS], index=0, key=f"{state_prefix}_filter")
    with col_reload:
        if st.button("Reload file", key=f"{state_prefix}_reload"):
            st.session_state[state_key] = file_load(state_prefix) or {}
            st.success("Reloaded from file.")
            st.rerun()
    with col_clear:
        if st.button("Clear saved file", key=f"{state_prefix}_clear"):
            file_clear(state_prefix)
            st.session_state[state_key] = {}
            st.success("Cleared saved file for this tab.")
            st.rerun()

    st.caption(f"Default base keywords: **{len(default_bases)}**")
    default_list = _filter_items(sorted(list(default_bases)), choice)
    _grid_render_bases(default_list)
    st.markdown("---")

    added_labels = [v["label"] for v in custom_dict.values()]
    display_added = _filter_items(added_labels, choice)
    st.caption(f"Your added base keywords: **{len(custom_dict)}**")
    if display_added:
        _grid_render_bases(display_added)
    else:
        st.info("No added keywords match this view.")

    st.markdown("### Manage your keywords")
    action = st.radio(
        "What do you want to do?",
        ["Add", "Edit variants/base", "Delete"],
        horizontal=True,
        key=f"{state_prefix}_action",
    )

    if action == "Add":
        with st.form(f"{state_prefix}_add_form", clear_on_submit=True):
            new_base = st.text_input("Base keyword")
            new_vars_txt = st.text_area("Variants (comma/semicolon/newline separated, optional)")
            add_clicked = st.form_submit_button("Add keyword")
        if add_clicked:
            base_label = (new_base or "").strip()
            if not base_label:
                st.warning("Please enter a base keyword.")
            else:
                base_key = _norm(base_label)
                default_norms = {_norm(x) for x in default_bases}
                if base_key in custom_dict:
                    st.warning("You already added this base keyword.")
                elif base_key in default_norms:
                    st.warning("This base keyword already exists in the default list.")
                else:
                    custom_dict[base_key] = {"label": base_label, "variants": _split_variants(new_vars_txt)}
                    st.session_state[state_key] = custom_dict
                    _persist(state_prefix, state_key)
                    st.success(f"Added **{base_label}**.")
                    st.rerun()

    elif action == "Edit variants/base":
        if not custom_dict:
            st.info("You haven't added any base keywords yet.")
        else:
            choices = sorted([v["label"] for v in custom_dict.values()], key=str.lower)
            sel_label = st.selectbox("Pick a base to edit", choices, key=f"{state_prefix}_edit_sel")
            sel_key = next(k for k, v in custom_dict.items() if v["label"] == sel_label)
            current_variants = custom_dict[sel_key]["variants"]

            prev_sel_key = f"{state_prefix}_edit_prev_sel"
            label_state_key = f"{state_prefix}_edit_label_state"
            vars_state_key = f"{state_prefix}_edit_vars_state"

            if st.session_state.get(prev_sel_key) != sel_label:
                st.session_state[label_state_key] = sel_label
                st.session_state[vars_state_key] = ", ".join(current_variants)
                st.session_state[prev_sel_key] = sel_label

            with st.form(f"{state_prefix}_edit_form", clear_on_submit=False):
                new_label = st.text_input("Base label", key=label_state_key)
                st.caption(f"Current variants ({len(current_variants)}):")
                if current_variants:
                    st.code(", ".join(current_variants), language="text")
                new_vars_txt = st.text_area(
                    "Replace variants (leave blank to clear all). Comma/semicolon/newline separated.",
                    key=vars_state_key
                )
                save_clicked = st.form_submit_button("Save")

            if save_clicked:
                new_label = (new_label or "").strip()
                new_key = _norm(new_label) if new_label else sel_key
                default_norms = {_norm(x) for x in default_bases}
                new_variants = _split_variants(new_vars_txt)

                if not new_label:
                    st.warning("Base label cannot be empty.")
                else:
                    if new_key != sel_key:
                        if new_key in custom_dict:
                            st.error("Another added base already uses that name.")
                            return
                        if new_key in default_norms:
                            st.error("That base name exists in the default list.")
                            return
                        custom_dict[new_key] = {"label": new_label, "variants": new_variants}
                        custom_dict.pop(sel_key, None)
                    else:
                        custom_dict[sel_key]["label"] = new_label
                        custom_dict[sel_key]["variants"] = new_variants

                    st.session_state[state_key] = custom_dict
                    _persist(state_prefix, state_key)
                    st.session_state.pop(prev_sel_key, None)
                    st.success("Saved.")
                    st.rerun()

    else:
        if not custom_dict:
            st.info("You haven't added any base keywords yet.")
        else:
            choices = sorted([v["label"] for v in custom_dict.values()], key=str.lower)
            mode = st.radio(
                "Delete mode",
                ["Whole base keyword", "Only specific variants"],
                horizontal=True,
                key=f"{state_prefix}_del_mode"
            )

            if mode == "Whole base keyword":
                del_label = st.selectbox("Pick a base to delete", choices, key=f"{state_prefix}_del_sel_base")
                with st.form(f"{state_prefix}_del_base_form", clear_on_submit=False):
                    confirm = st.checkbox("I understand this will remove the base and all its variants.",
                                          key=f"{state_prefix}_del_confirm")
                    del_clicked = st.form_submit_button("Delete base keyword")
                if del_clicked:
                    if not confirm:
                        st.warning("Please confirm before deleting.")
                    else:
                        del_key = next(k for k, v in custom_dict.items() if v["label"] == del_label)
                        custom_dict.pop(del_key, None)
                        st.session_state[state_key] = custom_dict
                        _persist(state_prefix, state_key)
                        st.success(f"Deleted **{del_label}**.")
                        st.rerun()
            else:
                del_label = st.selectbox("Pick a base to edit variants", choices, key=f"{state_prefix}_del_sel_vars")
                del_key = next(k for k, v in custom_dict.items() if v["label"] == del_label)
                current = custom_dict[del_key]["variants"]

                ms_key = f"{state_prefix}_del_vars_ms"
                prev_del_sel_key = f"{state_prefix}_del_prev_sel"
                if st.session_state.get(prev_del_sel_key) != del_label:
                    st.session_state[ms_key] = []
                    st.session_state[prev_del_sel_key] = del_label

                with st.form(f"{state_prefix}_del_vars_form", clear_on_submit=False):
                    if not current:
                        st.info("This base has no variants.")
                        del_selected = []
                        del_vars_clicked = st.form_submit_button("Delete selected variants", disabled=True)
                    else:
                        del_selected = st.multiselect("Select variants to remove", current, key=ms_key)
                        del_vars_clicked = st.form_submit_button("Delete selected variants")
                if del_vars_clicked:
                    if not del_selected:
                        st.warning("No variants selected.")
                    else:
                        custom_dict[del_key]["variants"] = [v for v in current if v not in del_selected]
                        st.session_state[state_key] = custom_dict
                        _persist(state_prefix, state_key)
                        st.success(f"Deleted {len(del_selected)} variant(s).")
                        st.rerun()
