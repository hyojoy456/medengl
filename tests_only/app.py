import sys
from pathlib import Path

# Ensure project root is on sys.path to allow `from utils.bank import ...`
sys.path.append(str(Path(__file__).resolve().parents[1]))

import streamlit as st
import random
from utils.bank import (
    BANK_NAMES,
    FINAL_TEST_QUESTION_LIMIT,
    dedupe_questions,
    get_random_questions_from_bank,
    get_random_questions_from_multiple,
)
from typing import Optional

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


def start_test_for_bank(bank_name: str, combined: bool = False, limit: Optional[int] = None) -> None:
    st.session_state.mode = "test"
    st.session_state.selected_bank = bank_name
    section = st.session_state.get("selected_section")
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


st.markdown(
    """
    <style>
    .square-btn > button { width: 100%; height: 110px; border-radius: 12px; font-size: 20px; font-weight: 600; }
    .bottom-btn > button { width: 100%; height: 64px; border-radius: 12px; font-size: 18px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


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
            correct_key = q.get("correct_key")
            correct_opt = next((o for o in q.get("options", []) if o.get("key") == correct_key), None)
            if correct_opt is not None:
                entry["correct_label"] = f"{correct_opt['key']}) {correct_opt['text']}"
            is_correct = entry["user"] == entry["correct_label"] if entry["correct_label"] else False
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
            correct_order = list(range(1, len(q.get("items", [])) + 1))
            user_positions = answers.get(idx) if isinstance(answers.get(idx), list) else []
            entry["correct_label"] = " → ".join([str(p) for p in correct_order])
            is_correct = user_positions == correct_order and len(correct_order) > 0
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

    bank_labels = [f"Module {i}" for i in range(1, 9)]
    for row in range(2):
        cols = st.columns(4, gap="large")
        for col_idx in range(4):
            i = row * 4 + col_idx
            with cols[col_idx]:
                if st.button(
                    bank_labels[i],
                    key=f"tests_home_med_bank_btn_{i}",
                    type="primary",
                    use_container_width=True,
                    help=f"Open {bank_labels[i]}",
                ):
                    start_test_for_bank(BANK_NAMES[i])

    st.divider()
    if st.button(
        "Final Test",
        key="tests_home_med_combined_btn",
        type="secondary",
        use_container_width=True,
        help="Random tasks across all 8 modules in this class",
    ):
        start_test_for_bank("combined", combined=True)

elif st.session_state.mode == "test":
    if st.session_state.get("selected_section"):
        st.button("Back", key="btn_back_to_modules", on_click=lambda: st.session_state.__setitem__("mode", "home"))
    else:
        st.button("← Home", key="btn_home_from_test", on_click=go_home)

    questions = st.session_state.questions
    idx = st.session_state.current_index

    st.header("Test")
    if not questions:
        st.info("No questions yet in this module.")
    else:
        total = len(questions)
        st.caption(f"Question {idx + 1}/15")
        q = questions[idx]
        st.write(q.get("text", ""))

        key = f"answer_{idx}"
        q_type = q.get("type")
        if q_type == "mcq" and q.get("options"):
            option_labels = [f"{opt['key']}) {opt['text']}" for opt in q["options"]]
            current = st.session_state.answers.get(idx)
            choice = st.radio(
                "Choose one option",
                options=option_labels,
                index=option_labels.index(current) if current in option_labels else None,
            )
            if choice:
                st.session_state.answers[idx] = choice
        elif q_type == "image_inputs" and q.get("images"):
            instr = (q.get("text") or "").strip()
            if instr:
                st.write(instr)
            imgs = q.get("images", [])
            cols = st.columns(len(imgs))
            for c_i, item in enumerate(imgs):
                with cols[c_i]:
                    url = item.get("url", "")
                    if url:
                        st.image(url, use_column_width=True)
                    ans_key = f"img_ans_{idx}_{c_i}"
                    value = st.text_input("Your answer", value=st.session_state.get(ans_key, ""), key=ans_key)
            st.session_state.answers[idx] = [
                st.session_state.get(f"img_ans_{idx}_{i}", "") for i in range(len(imgs))
            ]
        elif q_type == "ordering" and q.get("items"):
            instr = (q.get("text") or "Arrange the items in the correct order.").strip()
            if instr:
                st.write(instr)
            base_items = q.get("items", [])
            positions = []
            for item_i, item_text in enumerate(base_items):
                col1, col2 = st.columns([1, 5])
                with col1:
                    pos = st.number_input(
                        f"Pos {item_i+1}", min_value=1, max_value=len(base_items), step=1, key=f"tests_ord_pos_{idx}_{item_i}"
                    )
                    positions.append(int(pos))
                with col2:
                    st.text_input("Item", value=item_text, key=f"tests_ord_item_{idx}_{item_i}", disabled=True)
            st.session_state.answers[idx] = positions
        else:
            if q_type == "word_form":
                instr2 = (q.get("instruction") or "").strip()
                if instr2:
                    st.write(instr2)
                label = "Enter the word"
            else:
                label = "Your answer (free form)"
            value = st.text_input(label, value=st.session_state.get(key, ""), key=key)
            st.session_state.answers[idx] = value

        col_prev, col_next = st.columns([1, 1])
        with col_prev:
            st.button(
                "Back",
                key=f"btn_prev_{idx}",
                disabled=idx == 0,
                on_click=lambda: st.session_state.__setitem__("current_index", max(0, idx - 1)),
            )
        with col_next:
            if idx < total - 1:
                st.button(
                    "Next",
                    key=f"btn_next_{idx}",
                    on_click=lambda: st.session_state.__setitem__("current_index", min(total - 1, idx + 1)),
                )
            else:
                if st.button("Finish test", key="btn_finish_test"):
                    compute_results()
                    st.session_state.mode = "results"

elif st.session_state.mode == "results":
    st.title("Results")
    res = st.session_state.results or {"total": 0, "correct": 0, "details": []}
    st.subheader(f"Correct answers: {res['correct']} out of {res['total']}")
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
                st.caption(f"Your order: {d.get('user') or '—'} | Correct: {d.get('correct_label') or '—'}")
            else:
                st.markdown(f"ℹ️ Question {d['index']}: {d['text']}")
                st.caption(f"Your answer: {d.get('user') or '—'}")
            st.divider()
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.session_state.get("selected_section"):
            st.button("Back", key="btn_results_back_to_modules", on_click=lambda: st.session_state.__setitem__("mode", "home"))
        else:
            st.button("← Home", key="btn_results_home", on_click=go_home)
    with col2:
        st.button("Retake", key="btn_retake", on_click=lambda: start_test_for_bank(st.session_state.selected_bank, combined=(st.session_state.selected_bank == "combined")))


