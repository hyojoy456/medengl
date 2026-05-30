import streamlit as st
import random
from pathlib import Path
try:
    from streamlit_sortables import sort_items as _sort_items  # type: ignore
    _HAS_SORTABLES_LIB = True
except Exception:
    _HAS_SORTABLES_LIB = False
try:
    import pyarrow  # type: ignore  # noqa: F401
    _HAS_PYARROW = True
except Exception:
    _HAS_PYARROW = False
_HAS_SORTABLES = _HAS_SORTABLES_LIB and _HAS_PYARROW
from utils.bank import (
    BANK_NAMES,
    FINAL_TEST_QUESTION_LIMIT,
    dedupe_questions,
    get_banks_root,
    get_random_questions_from_bank,
    get_random_questions_from_multiple,
    ordering_items_row_html,
    theory_markdown_without_block_delimiters,
    mcq_is_multi_select,
)
from utils.md_images import render_inline_image, render_markdown_with_image_paths, markdown_preserve_newlines
from typing import Optional, cast

st.set_page_config(page_title="Tests", page_icon="🧪", layout="wide")

if "mode" not in st.session_state:
    st.session_state.mode = "home"
if "selected_section" not in st.session_state:
    st.session_state.selected_section = None
if "selected_bank" not in st.session_state:
    st.session_state.selected_bank = None
if "questions" not in st.session_state:
    st.session_state.questions = []
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "results" not in st.session_state:
    st.session_state.results = None
if "pending_bank" not in st.session_state:
    st.session_state.pending_bank = None
if "pending_section" not in st.session_state:
    st.session_state.pending_section = None
if "theory_resume_test" not in st.session_state:
    st.session_state.theory_resume_test = False


def _open_theory_from_test() -> None:
    st.session_state.theory_resume_test = True
    sb = st.session_state.get("selected_bank")
    if sb:
        st.session_state.pending_bank = sb
    st.session_state.pending_section = (
        st.session_state.get("selected_section")
        or st.session_state.get("pending_section")
        or "medical"
    )
    st.session_state.mode = "theory"


def _theory_back_to_test() -> None:
    st.session_state.mode = "test"
    st.session_state.theory_resume_test = False


def _theory_to_module_intro() -> None:
    st.session_state.mode = "module_intro"
    st.session_state.theory_resume_test = False


def start_test_for_bank(
    bank_name: str,
    combined: bool = False,
    limit: Optional[int] = None,
) -> None:
    """Start a test.

    * **Module** (``combined=False``): all unique questions from that bank, order by ``test_order``.
    * **Final test** (``combined=True``): random sample from the union of all banks (default size
      ``FINAL_TEST_QUESTION_LIMIT``). Pass ``limit`` to override the sample size for the final test,
      or to cap a module test (rare).
    """
    st.session_state.theory_resume_test = False
    st.session_state.mode = "test"
    st.session_state.selected_bank = bank_name
    section = st.session_state.get("selected_section")
    if not combined:
        st.session_state.pending_bank = bank_name
        st.session_state.pending_section = section or st.session_state.get("pending_section") or "medical"
    if combined:
        qs = get_random_questions_from_multiple(BANK_NAMES, limit=None, section=section)
        qs = dedupe_questions(qs, None)
        random.shuffle(qs)
        cap = limit if limit is not None else FINAL_TEST_QUESTION_LIMIT
        st.session_state.questions = qs[:cap]
    else:
        qs = get_random_questions_from_bank(bank_name, limit=None, section=section)
        st.session_state.questions = dedupe_questions(qs, limit)
    st.session_state.current_index = 0
    st.session_state.answers = {}


def go_home() -> None:
    st.session_state.mode = "home"
    st.session_state.selected_section = None
    st.session_state.selected_bank = None
    st.session_state.questions = []
    st.session_state.current_index = 0
    st.session_state.answers = {}
    st.session_state.pending_bank = None
    st.session_state.pending_section = None
    st.session_state.theory_resume_test = False


def open_module_intro(bank_name: str, section: Optional[str] = None) -> None:
    st.session_state.mode = "module_intro"
    st.session_state.pending_bank = bank_name
    st.session_state.pending_section = section or st.session_state.get("selected_section")


def load_theory_text(bank_name: str, section: Optional[str]) -> str:
    sec = section or st.session_state.get("selected_section") or "medical"
    theory_path = get_banks_root() / sec / "theory" / f"{bank_name}.md"
    try:
        if theory_path.exists():
            return theory_markdown_without_block_delimiters(theory_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    # Fallback placeholder
    idx = BANK_NAMES.index(bank_name) + 1 if bank_name in BANK_NAMES else 0
    return (
        f"### Theory for Module {idx}\n\n"
        f"Theory content has not been added yet. Ask your instructor to add the file "
        f"{bank_name}.md to banks/{sec}/theory/."
    )


_STUDENT_BASE_CSS = """
    .main .block-container { font-size: 1.125rem; line-height: 1.55; }
    .main h1 { font-size: 2.25rem !important; }
    .main h2 { font-size: 1.9rem !important; }
    .main h3 { font-size: 1.55rem !important; }
    .main [data-testid="stMarkdownContainer"] p,
    .main [data-testid="stMarkdownContainer"] li {
        font-size: 1.2rem;
        line-height: 1.6;
    }
    .main [data-testid="stMarkdownContainer"] h1 { font-size: 2rem !important; }
    .main [data-testid="stMarkdownContainer"] h2 { font-size: 1.75rem !important; }
    .main [data-testid="stMarkdownContainer"] h3 { font-size: 1.5rem !important; }
    .main .stTextInput input,
    .main .stTextArea textarea { font-size: 1.15rem !important; }
    .main [data-testid="stCaptionContainer"],
    .main .stCaption { font-size: 1.05rem !important; }
    .square-btn > button { width: 100%; height: 110px; border-radius: 12px; font-size: 20px; font-weight: 600; }
    .bottom-btn > button { width: 100%; height: 64px; border-radius: 12px; font-size: 18px; font-weight: 600; }
    .poster-wrapper { position: relative; display: inline-block; width: 100%; max-width: 760px; }
    .poster-wrapper img { width: 100%; height: auto; border-radius: 8px; display: block; }
    .poster-dot {
        position: absolute; transform: translate(-50%, -50%);
        width: 40px; height: 40px; border-radius: 50%;
        background: transparent; border: 2px solid #000000; color: #000000;
        font-weight: 800; font-size: 1.1rem;
        display: flex; align-items: center; justify-content: center;
        text-shadow: 0 0 3px rgba(255,255,255,0.9);
        box-shadow: inset 0 0 0 1px rgba(0,0,0,0.2);
    }
"""

_TEST_TASK_CSS = """
    .main [data-testid="stMarkdownContainer"] p,
    .main [data-testid="stMarkdownContainer"] li {
        font-size: 1.45rem !important;
        line-height: 1.65 !important;
    }
    .main [data-testid="stMarkdownContainer"] h1 { font-size: 2.15rem !important; }
    .main [data-testid="stMarkdownContainer"] h2 { font-size: 1.9rem !important; }
    .main [data-testid="stMarkdownContainer"] h3 { font-size: 1.65rem !important; }
    .main div[data-testid="stRadio"] label,
    .main div[data-testid="stRadio"] label p,
    .main div[data-testid="stRadio"] label span {
        font-size: 1.35rem !important;
        line-height: 1.5 !important;
    }
    .main div[data-testid="stCheckbox"] label,
    .main div[data-testid="stCheckbox"] label p,
    .main div[data-testid="stCheckbox"] label span {
        font-size: 1.35rem !important;
        line-height: 1.5 !important;
    }
    .main div[data-testid="stRadio"] > div {
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 0.5rem !important;
    }
    .main div[data-testid="stRadio"] label {
        align-items: flex-start !important;
        padding: 0.25rem 0 !important;
        width: 100% !important;
    }
    .main div[data-testid="stCheckbox"] {
        padding: 0.35rem 0 !important;
    }
    .main .stTextInput input { font-size: 1.25rem !important; min-height: 2.75rem; }
    .main [data-testid="stWidgetLabel"] p,
    .main label[data-testid="stWidgetLabel"] {
        font-size: 1.15rem !important;
    }
    .main [data-testid="stHeader"] { font-size: 2.1rem !important; }
"""

_THEORY_CSS = """
    .main [data-testid="stMarkdownContainer"] p,
    .main [data-testid="stMarkdownContainer"] li {
        font-size: 1.5rem !important;
        line-height: 1.7 !important;
    }
    .main [data-testid="stMarkdownContainer"] h1 { font-size: 2.15rem !important; }
    .main [data-testid="stMarkdownContainer"] h2 { font-size: 1.9rem !important; }
    .main [data-testid="stMarkdownContainer"] h3 { font-size: 1.7rem !important; }
    .main [data-testid="stMarkdownContainer"] strong { font-size: inherit; }
"""


def _inject_student_css(extra: str = "") -> None:
    st.markdown(f"<style>{_STUDENT_BASE_CSS}{extra}</style>", unsafe_allow_html=True)


_inject_student_css()
def render_poster_with_points(image_url: str, points: list[dict]) -> None:
    safe_url = image_url or ""
    if safe_url and not (safe_url.startswith("http://") or safe_url.startswith("https://")):
        try:
            p = Path(safe_url).expanduser()
            data = p.read_bytes()
            import base64
            b64 = base64.b64encode(data).decode("ascii")
            ext = p.suffix.lower()
            mime = "image/png" if ext not in [".jpg", ".jpeg", ".gif"] else ("image/jpeg" if ext in [".jpg", ".jpeg"] else "image/gif")
            safe_url = f"data:{mime};base64,{b64}"
        except Exception:
            pass
    # Build overlay HTML
    pts_sorted = sorted(points, key=lambda p: int(p.get("label", 0)))
    dots_html = "".join(
        [
            f"<div class='poster-dot' style='left:{float(p.get('x', 0))}%; top:{float(p.get('y', 0))}%;'>"\
            f"{int(p.get('label', i+1))}</div>"
            for i, p in enumerate(pts_sorted)
        ]
    )
    html = f"<div class='poster-wrapper'><img src='{safe_url}' alt='poster'/>{dots_html}</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_markdown_text(text: Optional[str]) -> None:
    """Render Markdown (**bold**, *italic*) and keep blank lines in the source text.

    CommonMark collapses extra blank lines; we turn newlines into hard breaks so
    line breaks from the admin text_area are preserved when shown to students.
    """
    raw = markdown_preserve_newlines(text or "")
    if not raw.strip():
        return
    st.markdown(raw, unsafe_allow_html=False)


def get_ordering_expected_answer(q: dict, idx: int) -> str:
    """Resolve expected ordering answer for a question.

    Priority:
    1) Explicit `answer_letters` from admin.
    2) Derived mapping from current shuffled display (legacy fallback).
    """
    items = q.get("items", []) or []
    if not items:
        return ""
    letters = [chr(ord("A") + i) for i in range(len(items))]
    stored = str(q.get("answer_letters") or "").strip().upper()
    if stored:
        allowed = set(letters)
        normalized = "".join([ch for ch in stored if ch in allowed])
        if normalized:
            return normalized
    order_key = f"ord_shuffle_{idx}"
    shuffled_idx = st.session_state.get(order_key)
    if not isinstance(shuffled_idx, list) or len(shuffled_idx) != len(items):
        shuffled_idx = list(range(len(items)))
    display_letter_for_original = [""] * len(items)
    for j, orig_i in enumerate(shuffled_idx):
        if 0 <= int(orig_i) < len(items):
            display_letter_for_original[int(orig_i)] = letters[j]
    return "".join(display_letter_for_original)



def compute_results() -> None:
    questions = st.session_state.questions
    answers = st.session_state.answers
    details = []
    correct_count = 0
    for idx, q in enumerate(questions):
        entry = {
            "index": idx + 1,
            "text": q.get("text", ""),
            "type": q.get("type"),
            "user": answers.get(idx),
            "correct": None,
            "correct_label": None,
        }
        q_type = q.get("type")
        if q_type == "mcq" and q.get("options"):
            user_val = answers.get(idx)
            option_labels = [f"{opt['key']}) {opt['text']}" for opt in q.get("options", [])]
            # Multi-answer support
            correct_keys = q.get("correct_keys") or ([q.get("correct_key")] if q.get("correct_key") else [])
            correct_keys = [str(k).lower() for k in correct_keys if str(k).strip()]
            # Compute correct indices and labels
            correct_idxs: list[int] = [i for i, opt in enumerate(q.get("options", [])) if str(opt.get("key")).lower() in correct_keys]
            correct_labels = [option_labels[i] for i in correct_idxs if 0 <= i < len(option_labels)]
            entry["correct_label"] = ", ".join(correct_labels)
            if isinstance(user_val, list):
                # user may have stored indices (ints) or labels; normalize to indices
                user_idxs: list[int] = []
                for u in user_val:
                    if isinstance(u, int):
                        user_idxs.append(u)
                    else:
                        if u in option_labels:
                            user_idxs.append(option_labels.index(u))
                entry["user"] = ", ".join([option_labels[i] for i in user_idxs if 0 <= i < len(option_labels)])
                is_correct = set(user_idxs) == set(correct_idxs) and len(correct_idxs) > 0
            else:
                # Single-answer mode stores label string
                entry["user"] = str(user_val)
                is_correct = (str(user_val) in correct_labels) and len(correct_labels) == 1
            entry["correct"] = is_correct
            if is_correct:
                correct_count += 1
        elif q_type == "word_form":
            correct_form = (q.get("answer") or "").strip().lower()
            user_ans = (answers.get(idx) or "").strip().lower()
            entry["correct_label"] = q.get("answer")
            is_correct = user_ans == correct_form and correct_form != ""
            entry["correct"] = is_correct
            if is_correct:
                correct_count += 1
        elif q_type == "image_inputs":
            expected = [((img.get("answer") or "").strip().lower()) for img in q.get("images", [])]
            user_vals_raw = answers.get(idx)
            user_list = user_vals_raw if isinstance(user_vals_raw, list) else []
            user_norm = [((u or "").strip().lower()) for u in user_list]
            entry["correct_label"] = ", ".join([img.get("answer") or "" for img in q.get("images", [])])
            is_correct = len(user_norm) == len(expected) and all(u == e for u, e in zip(user_norm, expected)) and len(expected) > 0
            entry["correct"] = is_correct
            if is_correct:
                correct_count += 1
        elif q_type == "ordering":
            # String-based ordering answer (e.g., "ACD"), sourced from admin answer_letters.
            user_value = answers.get(idx)
            if isinstance(user_value, str):
                expected_str = get_ordering_expected_answer(q, idx)
                entry["correct_label"] = expected_str
                entry["user"] = (user_value or "").strip().upper()
                is_correct = entry["user"] == expected_str and expected_str != ""
                entry["correct"] = is_correct
                if is_correct:
                    correct_count += 1
            else:
                correct_order = list(range(1, len(q.get("items", [])) + 1))
                user_positions = user_value if isinstance(user_value, list) else []
                entry["correct_label"] = " → ".join([str(p) for p in correct_order])
                is_correct = user_positions == correct_order and len(correct_order) > 0
                entry["correct"] = is_correct
                if is_correct:
                    correct_count += 1
        elif q_type == "poster":
            # Compare entered names to expected names (case-insensitive)
            pts = sorted(q.get("points", []), key=lambda p: int(p.get("label", 0)))
            expected_names = [(str(p.get("name") or "").strip().lower()) for p in pts]
            user_vals = answers.get(idx)
            user_names = user_vals if isinstance(user_vals, list) else []
            user_norm = [(str(n or "").strip().lower()) for n in user_names]
            entry["correct_label"] = ", ".join([p.get("name") or "" for p in pts])
            entry["user"] = ", ".join(user_names)
            is_correct = len(user_norm) == len(expected_names) and all(u == e for u, e in zip(user_norm, expected_names)) and len(expected_names) > 0
            entry["correct"] = is_correct
            if is_correct:
                correct_count += 1
        details.append(entry)
    st.session_state.results = {
        "total": len(questions),
        "correct": correct_count,
        "details": details,
    }


if st.session_state.mode == "home":
    # Single-class home: Medical only
    st.session_state.selected_section = "medical"
    st.markdown("<h1 style='text-align:center;'>Medical class</h1>", unsafe_allow_html=True)

    st.subheader("Choose module")

    bank_labels = [
        "1. Research",
        "2. First Aid Kit",
        "3. Jobs",
        "4. Toxins",
        "Module 5",
        "Module 6",
        "Module 7",
        "Module 8",
    ]
    for row in range(2):
        cols = st.columns(4, gap="large")
        for col_idx in range(4):
            i = row * 4 + col_idx
            with cols[col_idx]:
                if st.button(
                    bank_labels[i],
                    key=f"home_med_bank_btn_{i}",
                    type="primary",
                    use_container_width=True,
                    help=f"Open {bank_labels[i]}",
                ):
                    open_module_intro(BANK_NAMES[i], section=st.session_state.get("selected_section"))

    st.divider()
    if st.button(
        "Final Test",
        key="home_med_combined_btn",
        type="secondary",
        use_container_width=True,
        help="Random questions from all 8 module banks",
    ):
        start_test_for_bank("combined", combined=True)

    st.caption("Each module includes theory and a practice test.")

elif st.session_state.mode == "section_home":
    section = st.session_state.get("selected_section") or "engineers"
    titles = {"medical": "Medical class"}
    st.button("← Back", on_click=go_home)
    st.header(titles.get(section, "Section"))
    st.subheader("Choose module")

    bank_labels = [
        "1. Research",
        "2. First Aid Kit",
        "3. Jobs",
        "4. Toxins",
        "Module 5",
        "Module 6",
        "Module 7",
        "Module 8",
    ]
    for row in range(2):
        cols = st.columns(4, gap="large")
        for col_idx in range(4):
            i = row * 4 + col_idx
            with cols[col_idx]:
                if st.button(
                    bank_labels[i],
                    key=f"sec_bank_btn_{section}_{i}",
                    type="primary",
                    use_container_width=True,
                    help=f"Open {bank_labels[i]}",
                ):
                    open_module_intro(BANK_NAMES[i], section=section)

    st.divider()
    if st.button(
        "Final Test",
        key=f"combined_btn_{section}",
        type="secondary",
        use_container_width=True,
        help="Random questions from all 8 module banks",
    ):
        start_test_for_bank("combined", combined=True)

elif st.session_state.mode == "module_intro":
    section = st.session_state.get("pending_section") or "medical"
    bank = st.session_state.get("pending_bank") or BANK_NAMES[0]
    idx = BANK_NAMES.index(bank) + 1 if bank in BANK_NAMES else 0
    st.button("Back", on_click=lambda: st.session_state.__setitem__("mode", "home"))
    st.header(f"Module {idx}")
    st.caption("Review the theory before starting the test")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("💡 Open theory", type="secondary", use_container_width=True, on_click=lambda: st.session_state.__setitem__("mode", "theory"))
    with col2:
        st.button("Start the Test", type="primary", use_container_width=True, on_click=lambda: start_test_for_bank(bank))

elif st.session_state.mode == "theory":
    section = st.session_state.get("pending_section") or "medical"
    bank = st.session_state.get("pending_bank") or BANK_NAMES[0]
    resume = st.session_state.get("theory_resume_test")
    if resume:
        nav_a, nav_b = st.columns(2)
        with nav_a:
            st.button(
                "← Back to test",
                type="primary",
                use_container_width=True,
                on_click=_theory_back_to_test,
            )
        with nav_b:
            st.button("To module", use_container_width=True, on_click=_theory_to_module_intro)
    else:
        st.button(
            "Back",
            use_container_width=True,
            on_click=lambda: st.session_state.__setitem__("mode", "module_intro"),
        )
    st.header("Theory")
    _inject_student_css(_THEORY_CSS)
    render_markdown_with_image_paths(load_theory_text(bank, section))
    st.divider()
    if not resume:
        st.button("Start the Test", type="primary", use_container_width=True, on_click=lambda: start_test_for_bank(bank))

elif st.session_state.mode == "test":
    _inject_student_css(_TEST_TASK_CSS)
    sb_test = st.session_state.get("selected_bank")
    show_theory_btn = bool(sb_test and sb_test != "combined")
    if show_theory_btn:
        st.button(
            "💡 To theory",
            use_container_width=True,
            on_click=_open_theory_from_test,
        )

    questions = st.session_state.questions
    idx = st.session_state.current_index

    st.header("Test")
    if not questions:
        st.info("This module has no questions yet. Go back to the home page or ask your instructor to add tasks in Admin.")
        st.divider()
        if st.session_state.get("selected_section"):
            st.button(
                "Back to the main menu",
                type="secondary",
                use_container_width=True,
                on_click=lambda: st.session_state.__setitem__("mode", "home"),
            )
        else:
            st.button("Back to the main menu", type="secondary", use_container_width=True, on_click=go_home)
    else:
        total = len(questions)
        st.caption(f"Question {idx + 1}/{total}")
        q = questions[idx]
        render_markdown_text(q.get("text"))

        key = f"answer_{idx}"
        q_type = q.get("type")
        if q_type == "mcq" and q.get("options"):
            option_labels = [f"{opt['key']}) {opt['text']}" for opt in q["options"]]
            is_multi = mcq_is_multi_select(q)
            if is_multi:
                st.caption("Select all correct options")
                selected: list[int] = []
                preselected_raw = st.session_state.answers.get(idx)
                preselected = preselected_raw if isinstance(preselected_raw, list) else []
                for i, opt in enumerate(q["options"]):
                    label = f"{opt['key']}) {opt.get('text', '')}"
                    if st.checkbox(
                        label,
                        value=(i in preselected),
                        key=f"mcq_{idx}_{i}",
                    ):
                        selected.append(i)
                st.session_state.answers[idx] = selected
            else:
                current = st.session_state.answers.get(idx)
                cur_idx = option_labels.index(current) if current in option_labels else 0
                choice_idx = st.radio(
                    "Select one option",
                    options=list(range(len(option_labels))),
                    index=cur_idx,
                    format_func=lambda i: option_labels[i],
                    label_visibility="collapsed",
                    key=f"mcq_radio_keys_{idx}",
                )
                if choice_idx is not None:
                    st.session_state.answers[idx] = option_labels[int(choice_idx)]
        elif q_type == "image_inputs" and q.get("images"):
            imgs = q.get("images", [])
            cols = st.columns(len(imgs))
            for c_i, item in enumerate(imgs):
                with cols[c_i]:
                    url = item.get("url", "")
                    if url:
                        render_inline_image(url)
                    ans_key = f"img_ans_{idx}_{c_i}"
                    # Always render an empty field for the user (ignore any preset answer)
                    value = st.text_input("Your answer", value=st.session_state.get(ans_key, ""), key=ans_key)
            st.session_state.answers[idx] = [
                st.session_state.get(f"img_ans_{idx}_{i}", "") for i in range(len(imgs))
            ]
        elif q_type == "ordering" and q.get("items"):
            items = q.get("items", [])
            # Shuffle items once per question to present randomly with letter labels
            order_key = f"ord_shuffle_{idx}"
            if order_key not in st.session_state:
                shuffled = list(range(len(items)))
                random.shuffle(shuffled)
                st.session_state[order_key] = shuffled
            shuffled_idx = st.session_state[order_key]
            letters = [chr(ord('A') + i) for i in range(len(items))]

            st.markdown(
                ordering_items_row_html(items, shuffled_idx, letters),
                unsafe_allow_html=True,
            )
            ans = st.text_input("Enter the correct sequence (e.g., ACD)", key=f"ord_seq_{idx}")
            st.session_state.answers[idx] = (ans or "").strip().upper()
        elif q_type == "poster" and q.get("image_url") and q.get("points"):
            pts = sorted(q.get("points", []), key=lambda p: int(p.get("label", 0)))
            render_poster_with_points(q.get("image_url"), pts)
            values: list[str] = []
            for i, _ in enumerate(pts):
                val = st.text_input(f"Name {i + 1}", key=f"poster_name_input_{idx}_{i}")
                values.append(val)
            st.session_state.answers[idx] = values
        else:
            if q_type == "word_form":
                instr2 = (q.get("instruction") or "").strip()
                if instr2:
                    render_markdown_text(instr2)
                label = "Enter the word"
            else:
                label = "Your answer (free form)"
            value = st.text_input(label, value=st.session_state.get(key, ""), key=key)
            st.session_state.answers[idx] = value

        if idx < total - 1:
            st.button(
                "Next",
                use_container_width=True,
                on_click=lambda: st.session_state.__setitem__("current_index", min(total - 1, idx + 1)),
            )
        else:
            if st.button("Finish test", use_container_width=True):
                compute_results()
                st.session_state.mode = "results"

        st.divider()
        if st.session_state.get("selected_section"):
            st.button(
                "Back to the main menu",
                type="secondary",
                use_container_width=True,
                on_click=lambda: st.session_state.__setitem__("mode", "home"),
            )
        else:
            st.button("Back to the main menu", type="secondary", use_container_width=True, on_click=go_home)

elif st.session_state.mode == "results":
    st.title("Results")
    res = st.session_state.results or {"total": 0, "correct": 0, "details": []}
    st.subheader(f"Correct answers: {res['correct']} of {res['total']}")
    with st.expander("Question details", expanded=False):
        for d in res["details"]:
            if d.get("type") == "mcq":
                status = "✅" if d.get("correct") else "❌"
                st.markdown(f"{status} Question {d['index']}: {d['text']}")
                st.caption(f"Your answer: {d.get('user') or '—'} | Correct: {d.get('correct_label') or '—'}")
            elif d.get("type") == "word_form":
                status = "✅" if d.get("correct") else "❌"
                st.markdown(f"{status} Question {d['index']}: {d['text']}")
                st.caption(f"Your answer: {d.get('user') or '—'} | Correct: {d.get('correct_label') or '—'}")
            elif d.get("type") == "image_inputs":
                status = "✅" if d.get("correct") else "❌"
                st.markdown(f"{status} Question {d['index']}: (images)")
                st.caption(f"Your answers: {d.get('user') or '—'}")
            elif d.get("type") == "ordering":
                status = "✅" if d.get("correct") else "❌"
                st.markdown(f"{status} Question {d['index']}: (ordering)")
                st.caption(f"Your sequence: {d.get('user') or '—'} | Correct: {d.get('correct_label') or '—'}")
            elif d.get("type") == "poster":
                status = "✅" if d.get("correct") else "❌"
                st.markdown(f"{status} Question {d['index']}: (poster)")
                st.caption(f"Your names: {d.get('user') or '—'} | Correct: {d.get('correct_label') or '—'}")
            else:
                st.markdown(f"ℹ️ Question {d['index']}: {d['text']}")
                st.caption(f"Your answer: {d.get('user') or '—'}")
            st.divider()
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.session_state.get("selected_section"):
            st.button("Back", on_click=lambda: st.session_state.__setitem__("mode", "home"))
        else:
            st.button("← Home", on_click=go_home)
    with col2:
        st.button("Retake test", on_click=lambda: start_test_for_bank(st.session_state.selected_bank, combined=(st.session_state.selected_bank == "combined")))
