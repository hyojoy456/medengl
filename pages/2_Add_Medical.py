import streamlit as st
from utils.bank import (
    BANK_NAMES,
    add_mcq_question,
    parse_pasted_mcq,
    load_bank,
    sort_questions_for_test,
    set_questions_test_orders,
    ordering_items_row_html,
    parse_positive_test_order,
    coerce_order_field_int,
    mcq_is_multi_select,
    add_word_form_question,
    add_image_inputs_question,
    delete_question,
    update_question_fields,
    add_ordering_question,
    add_poster_question,
    append_theory_block,
    delete_theory_markdown,
    load_theory_blocks,
    delete_theory_block,
    update_theory_block,
    get_banks_root,
    POSTER_POINT_SLOTS,
    POSTER_POINT_COUNT_MIN,
    IMAGE_INPUTS_MIN,
    IMAGE_INPUTS_MAX,
)
import base64
from utils.md_images import (
    markdown_preserve_newlines,
    render_markdown_with_image_paths,
    save_uploaded_theory_image,
)
try:
    from streamlit_drawable_canvas import st_canvas  # type: ignore
    _HAS_CANVAS = True
except Exception:
    _HAS_CANVAS = False
try:
    from PIL import Image  # type: ignore
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False
import io
import requests
from typing import Any, Optional
import os
import uuid

st.set_page_config(page_title="Add Tasks — Medical", page_icon="🧬", layout="wide")

SECTION = "medical"


def _admin_rerun() -> None:
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()


def _show_admin_flash() -> None:
    payload = st.session_state.pop("_admin_flash", None)
    if not payload:
        return
    kind, msg = payload
    if kind == "error":
        st.error(msg)
    elif kind == "success":
        st.success(msg)


def _delete_question_cb(bname: str, qid: str) -> None:
    try:
        ok = delete_question(bname, qid, section=SECTION)
    except OSError as exc:
        st.session_state["_admin_flash"] = (
            "error",
            "Не удалось сохранить файл с заданиями. "
            "На Streamlit Cloud изменения в файлах временные — для постоянного удаления "
            f"отредактируйте банк локально и отправьте на GitHub. ({exc})",
        )
        return
    if not ok:
        st.session_state["_admin_flash"] = ("error", "Задание не найдено (возможно, уже удалено).")
        return
    edit_key = f"question_edit_id_{bname}_{SECTION}"
    if str(st.session_state.get(edit_key) or "") == str(qid):
        st.session_state[edit_key] = None


st.title("Конструктор заданий для преподавателя")
_show_admin_flash()

bank_label_to_name = {f"Module {i}": name for i, name in enumerate(BANK_NAMES, start=1)}
label = st.selectbox("Выберите модуль", list(bank_label_to_name.keys()), index=0)
assert label is not None
bank_name = bank_label_to_name[label]

_MCQ_STEP_KEY = f"mcq_admin_step_{SECTION}"
_MCQ_DRAFT_KEY = f"mcq_admin_draft_{SECTION}"

if _MCQ_STEP_KEY not in st.session_state:
    st.session_state[_MCQ_STEP_KEY] = 1

st.subheader("Добавьте задание закрытого типа")

if st.session_state[_MCQ_STEP_KEY] == 1:
    with st.form("add_mcq_step1", clear_on_submit=False):
        q_text_field = st.text_area("Текст вопроса", height=100)
        colA, colB, colC = st.columns(3)
        with colA:
            opt_a = st.text_input("A)")
            opt_d = st.text_input("D) (необязательно)")
        with colB:
            opt_b = st.text_input("B)")
            opt_e = st.text_input("E) (необязательно)")
        with colC:
            opt_c = st.text_input("C)")
            opt_f = st.text_input("F) (необязательно)")
        st.markdown(
            '<p style="font-size:1.45rem;font-weight:600;margin:1.25rem 0 0.75rem 0;">'
            "Сколько правильных ответов?</p>",
            unsafe_allow_html=True,
        )
        answer_mode = st.radio(
            "Тип правильного ответа",
            ["Один правильный ответ", "Несколько правильных ответов"],
            label_visibility="collapsed",
        )
        submitted_mcq_step1 = st.form_submit_button("Далее")
        st.caption('Нажмите «Далее» для выбора правильных ответов на задание')
    if submitted_mcq_step1:
        if not q_text_field.strip() or not opt_a.strip() or not opt_b.strip() or not opt_c.strip():
            st.error("Заполните минимум A, B, C и текст вопроса")
        else:
            opts = []
            for key, val in [
                ("a", opt_a),
                ("b", opt_b),
                ("c", opt_c),
                ("d", opt_d),
                ("e", opt_e),
                ("f", opt_f),
            ]:
                if str(val).strip():
                    opts.append({"key": key, "text": str(val).strip()})
            if len(opts) < 2:
                st.error("Нужно минимум 2 варианта ответа")
            else:
                st.session_state[_MCQ_DRAFT_KEY] = {
                    "text": q_text_field.strip(),
                    "options": opts,
                    "multi": answer_mode == "Несколько правильных ответов",
                }
                st.session_state[_MCQ_STEP_KEY] = 2
                _admin_rerun()
else:
    draft = st.session_state.get(_MCQ_DRAFT_KEY)
    if not draft or not draft.get("options"):
        st.session_state[_MCQ_STEP_KEY] = 1
        _admin_rerun()
    else:
        st.markdown("#### Выберите правильные ответы для задания")
        st.caption(f"Вопрос: {draft.get('text', '')[:120]}{'…' if len(draft.get('text', '')) > 120 else ''}")
        opts = draft["options"]
        multi = bool(draft.get("multi"))
        with st.form("add_mcq_step2", clear_on_submit=False):
            if multi:
                st.caption("Отметьте все правильные варианты")
                for o in opts:
                    k = str(o["key"]).lower()
                    st.checkbox(f"{k.upper()}) {o.get('text', '')}", key=f"mcq_corr_{k}_{bank_name}")
            else:
                labels = [f"{o['key']}) {o.get('text', '')}" for o in opts]
                keys = [str(o["key"]).lower() for o in opts]
                st.radio(
                    "Правильный ответ",
                    options=keys,
                    format_func=lambda k: labels[keys.index(k)],
                    label_visibility="collapsed",
                    key=f"mcq_pick_{bank_name}",
                )
            col_back, col_save = st.columns(2)
            with col_back:
                back_step2 = st.form_submit_button("← Назад")
            with col_save:
                save_mcq = st.form_submit_button("Сохранить задание", type="primary")
        if back_step2:
            st.session_state[_MCQ_STEP_KEY] = 1
            _admin_rerun()
        if save_mcq:
            correct_keys_field: list[str] = []
            if multi:
                for o in opts:
                    k = str(o["key"]).lower()
                    if st.session_state.get(f"mcq_corr_{k}_{bank_name}"):
                        correct_keys_field.append(k)
            else:
                pick = st.session_state.get(f"mcq_pick_{bank_name}")
                if pick:
                    correct_keys_field = [str(pick)]
            if not correct_keys_field:
                st.error("Выберите хотя бы один правильный ответ")
            elif multi and len(correct_keys_field) < 2:
                st.error("Для режима «несколько ответов» отметьте минимум два варианта")
            else:
                add_mcq_question(
                    bank_name,
                    draft["text"],
                    opts,
                    correct_keys_field,
                    section=SECTION,
                    allow_multiple=multi,
                )
                st.session_state[_MCQ_STEP_KEY] = 1
                st.session_state.pop(_MCQ_DRAFT_KEY, None)
                st.success("Вопрос (закрытый тип) добавлен")
                _admin_rerun()

st.divider()

st.subheader("Добавьте задание открытого типа")
with st.form("add_word_form_med_add", clear_on_submit=True):
    wf_text = st.text_area("Текст вопроса", height=140)
    correct = st.text_input("Правильный ответ")
    submitted_wf = st.form_submit_button("Далее")
    if submitted_wf:
        if not wf_text.strip() or not correct.strip():
            st.error("Заполните все поля")
        else:
            add_word_form_question(
                bank_name,
                wf_text or "",
                correct.strip(),
                section=SECTION,
            )
            st.success("Word Form задание добавлено в медицинский раздел")

st.divider()

st.subheader("Добавьте задание на сопоставление изображений")
with st.form("add_image_inputs_med", clear_on_submit=False):
    st.caption(
        f"Загрузите от {IMAGE_INPUTS_MIN} до {IMAGE_INPUTS_MAX} файлов изображений и укажите ОБЯЗАТЕЛЬНО ответ к каждому. Регистр не важен."
    )
    instr = st.text_area("Текст вопроса", height=80)
    files = st.file_uploader("Изображения", type=["png", "jpg", "jpeg", "gif"], accept_multiple_files=True)
    num = len(files) if files else 0
    ans_inputs = []
    for i in range(min(IMAGE_INPUTS_MAX, num)):
        ans_inputs.append(st.text_input(f"Ответ {i+1}", key=f"img_ans_u_{i}"))
    submitted_imgs = st.form_submit_button("Далее")
    if submitted_imgs:
        if not files or len(files) < IMAGE_INPUTS_MIN:
            st.error(f"Нужно минимум {IMAGE_INPUTS_MIN} изображения")
        elif len(files) > IMAGE_INPUTS_MAX:
            st.error(f"Не более {IMAGE_INPUTS_MAX} изображений")
        else:
            media_dir = str(get_banks_root() / "media")
            os.makedirs(media_dir, exist_ok=True)
            # Validate that every image has an answer
            need = min(IMAGE_INPUTS_MAX, len(files))
            missing = [i + 1 for i in range(need) if i >= len(ans_inputs) or not (ans_inputs[i] or "").strip()]
            if missing:
                st.error("Заполните ответы для всех изображений: отсутствует ответ для № " + ", ".join(map(str, missing)))
            else:
                items = []
                for i, f in enumerate(files[:IMAGE_INPUTS_MAX]):
                    answer_text = ans_inputs[i] if i < len(ans_inputs) else ""
                    ext = os.path.splitext(f.name)[1] or ".png"
                    fname = f"img_{uuid.uuid4().hex}_{i}{ext}"
                    path = os.path.join(media_dir, fname)
                    try:
                        data = f.getbuffer() if hasattr(f, "getbuffer") else f.read()
                        with open(path, "wb") as out:
                            out.write(data)
                        items.append({"url": path, "answer": answer_text})
                    except Exception:
                        pass
                if len(items) < IMAGE_INPUTS_MIN:
                    st.error(f"Нужно минимум {IMAGE_INPUTS_MIN} изображения с ответами")
                else:
                    add_image_inputs_question(bank_name, items, section="medical", instruction_text=instr or "")
                    st.success("Вопрос с изображениями добавлен в медицинский раздел")

st.divider()

st.subheader("Добавьте задание на восстановление последовательности")
st.caption("Укажите фразы и один правильный ответ в виде набора букв. Ученик увидит фразы в случайном порядке и введёт правильную последовательность.")
with st.form("add_ordering_med_v3", clear_on_submit=True):
    ord_instr = st.text_area("Текст вопроса", height=80, value="Arrange the sentences in the correct order.")
    count = st.number_input("Количество фраз", min_value=3, max_value=6, step=1, value=3)
    phrase_inputs = []
    for i in range(int(count)):
        phrase_inputs.append(st.text_area(f"Фраза {i+1}", height=70, key=f"ord_phrase_{i}"))
    st.caption("Введите правильную последовательность букв без пробелов (например, ABCD)")
    correct_letters = st.text_input("Правильный ответ")
    submitted_ord = st.form_submit_button("Сохранить")
    if submitted_ord:
        items = [str(s) for s in phrase_inputs if str(s).strip()]
        if len(items) < 3:
            st.error("Нужно от 3 до 6 непустых фраз")
        else:
            answer_raw = (correct_letters or "").strip().upper()
            allowed = {chr(ord("A") + i) for i in range(len(items))}
            answer_norm = "".join([ch for ch in answer_raw if ch in allowed])
            if not answer_norm:
                st.error("Укажите правильную последовательность")
            elif len(answer_norm) != len(items):
                st.error(f"Ответ должен содержать ровно {len(items)} букв: {''.join(sorted(allowed))}")
            elif len(set(answer_norm)) != len(answer_norm):
                st.error("В последовательности не должно быть повторяющихся букв")
            else:
                add_ordering_question(
                    bank_name,
                    items,
                    section=SECTION,
                    instruction_text=ord_instr or "",
                    answer_letters=answer_norm,
                )
                st.success("Задание на упорядочивание добавлено")

# Небольшой предпросмотр: как увидит ученик (случайная перестановка)
with st.expander("Предпросмотр отображения для ученика", expanded=False):
    demo_items = [st.session_state.get(f"ord_phrase_{i}", "") for i in range(6)]
    demo_items = [s for s in demo_items if str(s).strip()]
    if len(demo_items) >= 3:
        import random as _r
        _idxs = list(range(len(demo_items)))
        _r.shuffle(_idxs)
        letters = [chr(ord('A') + i) for i in range(len(demo_items))]
        st.markdown(
            ordering_items_row_html(demo_items, _idxs, letters),
            unsafe_allow_html=True,
        )
        st.caption("Ответ ученика будет строкой из букв, например: ABC")

st.divider()

st.subheader("Добавьте задание-постер")
st.caption(
    f"Загрузите картинку. На предпросмотре — сетка с номерами. Ниже сразу {POSTER_POINT_SLOTS} точек: "
    f"заполните номер на сетке и название минимум для {POSTER_POINT_COUNT_MIN} точек (пустые строки пропускаются)."
)
poster_instr = st.text_area("Текст вопроса", height=80, value="Attach organ's name and description with the numbered circles.")
col_img_src1, col_img_src2 = st.columns([2, 1])
with col_img_src1:
    poster_img_url = st.text_input("URL картинки (необязательно)")
with col_img_src2:
    poster_img_file = st.file_uploader("Или загрузите файл", type=["png", "jpg", "jpeg"])

# Resolve image source to bytes and size
canvas_image = None
bytes_data = None
img_width = 600
img_height = 360
resolved_url = poster_img_url.strip()
if poster_img_file is not None:
    try:
        bytes_data = poster_img_file.read()
        if _HAS_PIL:
            canvas_image = Image.open(io.BytesIO(bytes_data)).convert("RGBA")
            img_width, img_height = canvas_image.size
    except Exception:
        canvas_image = None

st.caption("Предпросмотр с нумерованной сеткой")
bg_image = None
if canvas_image is not None:
    bg_image = canvas_image
elif resolved_url and _HAS_PIL:
    try:
        resp = requests.get(resolved_url, timeout=10)
        resp.raise_for_status()
        canvas_image = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        img_width, img_height = canvas_image.size
        bg_image = canvas_image
    except Exception:
        bg_image = None
        # Fallback preview via HTML to avoid numpy dependency
        st.markdown(f"<img src='{resolved_url}' style='width:100%; border-radius:8px;' />", unsafe_allow_html=True)

def _with_grid(img: "Image.Image"):
    try:
        grid = img.copy()
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(grid, "RGBA")
        w, h = grid.size
        # Lines every 10%
        for t in range(0, 101, 10):
            x = int(w * t / 100)
            y = int(h * t / 100)
            draw.line([(x, 0), (x, h)], fill=(0, 255, 0, 90), width=1)
            draw.line([(0, y), (w, y)], fill=(0, 255, 0, 90), width=1)
        # Bigger labels at cell centers (every 10%)
        try:
            font_size = max(12, int(min(w, h) * 0.035))
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        for gx in range(0, 100, 10):
            for gy in range(0, 100, 10):
                cx = int(w * (gx + 5) / 100)
                cy = int(h * (gy + 5) / 100)
                label = f"{gx+5},{gy+5}"
                # center text
                try:
                    bbox = draw.textbbox((0, 0), label, font=font)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                except Exception:
                    tw, th = 40, 16
                draw.rectangle((cx - tw / 2 - 3, cy - th / 2 - 3, cx + tw / 2 + 3, cy + th / 2 + 3), fill=(0, 0, 0, 120))
                draw.text((cx - tw / 2, cy - th / 2), label, fill=(255, 255, 0, 220), font=font)
        return grid
    except Exception:
        return img

def _with_number_grid(
    img: "Image.Image",
    cols: int = 21,
    rows: int = 10,
    start_label: int = 1,
    end_label: int = 300,
):
    try:
        grid = img.copy()
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(grid, "RGBA")
        w, h = grid.size
        cell_w = w / cols
        cell_h = h / rows
        # draw grid lines
        for c in range(cols + 1):
            x = int(c * cell_w)
            draw.line([(x, 0), (x, h)], fill=(0, 255, 0, 90), width=1)
        for r in range(rows + 1):
            y = int(r * cell_h)
            draw.line([(0, y), (w, y)], fill=(0, 255, 0, 90), width=1)
        # Fixed font as requested: Times New Roman, size 16
        font = None
        for name in [
            "Times New Roman.ttf",
            "TimesNewRoman.ttf",
            "TimesNewRomanPSMT.ttf",
            "Times.ttf",
        ]:
            try:
                font = ImageFont.truetype(name, 6)
                break
            except Exception:
                continue
        if font is None:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", 6)
            except Exception:
                font = ImageFont.load_default()
        span = max(1, (end_label - start_label + 1))
        for r in range(rows):
            for c in range(cols):
                label = start_label + ((r * cols + c) % span)
                cx = int((c + 0.5) * cell_w)
                cy = int((r + 0.5) * cell_h)
                txt = str(label)
                try:
                    bbox = draw.textbbox((0, 0), txt, font=font)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                except Exception:
                    tw, th = 18, 12
                # draw a subtle shadow for readability (no opaque rectangles)
                draw.text((cx - tw / 2 + 1, cy - th / 2 + 1), txt, fill=(0, 0, 0, 160), font=font)
                # bright orange text
                draw.text((cx - tw / 2, cy - th / 2), txt, fill=(255, 140, 0, 240), font=font)
        return grid
    except Exception:
        return img

def _code_to_percent(code: int, cols: int = 21, rows: int = 10, start_label: int = 1) -> tuple[float, float]:
    # Map a label number to a cell position (wrap if exceeds total cells)
    idx = max(0, code - start_label)
    total = cols * rows
    if total <= 0:
        total = 1
    idx = idx % total
    c = idx % cols
    r = idx // cols
    x = (c + 0.5) / cols * 100.0
    y = (r + 0.5) / rows * 100.0
    return x, y

# Render numbered grid preview with user-configurable range
grid_max = int(st.number_input("Максимальный номер на сетке", min_value=1, max_value=10000, step=1, value=300, key="poster_grid_max"))
if _HAS_PIL and (bg_image is not None):
    try:
        grid = _with_number_grid(bg_image, start_label=1, end_label=grid_max)
        buf = io.BytesIO()
        grid.save(buf, format="PNG")
        data = buf.getvalue()
        import base64 as _b64
        b64 = _b64.b64encode(data).decode("ascii")
        st.markdown(f"<img src='data:image/png;base64,{b64}' style='width:100%; border-radius:8px;' />", unsafe_allow_html=True)
    except Exception:
        pass
elif resolved_url:
    st.markdown(f"<img src='{resolved_url}' style='width:100%; border-radius:8px;' />", unsafe_allow_html=True)

click_points = []  # legacy clicks no longer used

point_data: list[dict[str, Any]] = []
for i in range(POSTER_POINT_SLOTS):
    st.markdown(f"**Точка {i + 1}**")
    pc1, pc2 = st.columns([1, 2])
    with pc1:
        code = int(
            st.number_input(
                f"Номер на сетке (1–{grid_max})",
                min_value=1,
                max_value=grid_max,
                step=1,
                value=1,
                key=f"p_code_{bank_name}_{i}",
            )
        )
    with pc2:
        name = st.text_input(f"Название {i + 1}", key=f"p_name_{bank_name}_{i}")
    px, py = _code_to_percent(code, start_label=1)
    point_data.append({"label": i + 1, "x": float(px), "y": float(py), "name": name, "description": "", "code": code})

submitted_poster2 = st.button("Сохранить постер-задание")
if submitted_poster2:
    filled: list[dict[str, Any]] = []
    for i in range(POSTER_POINT_SLOTS):
        row = point_data[i]
        nm = str(row.get("name") or "").strip()
        if not nm:
            continue
        code = int(row.get("code") or 1)
        px, py = _code_to_percent(code, start_label=1)
        filled.append({"label": len(filled) + 1, "x": float(px), "y": float(py), "name": nm, "description": ""})
    if len(filled) < POSTER_POINT_COUNT_MIN:
        st.error(f"Укажите названия минимум для {POSTER_POINT_COUNT_MIN} точек (сейчас заполнено: {len(filled)}).")
    elif not resolved_url and poster_img_file is None:
        st.error("Задайте картинку через URL или загрузите файл")
    else:
        final_image_url = resolved_url
        if poster_img_file is not None and not final_image_url:
            media_dir = str(get_banks_root() / "media")
            import os
            os.makedirs(media_dir, exist_ok=True)
            fname = f"poster_{bank_name}.png"
            path = os.path.join(media_dir, fname)
            try:
                if _HAS_PIL and canvas_image is not None:
                    canvas_image.save(path)
                elif bytes_data is not None:
                    with open(path, "wb") as f:
                        f.write(bytes_data)
                final_image_url = path
            except Exception:
                final_image_url = ""
        try:
            add_poster_question(bank_name, final_image_url, filled, section=SECTION, instruction_text=poster_instr or "")
            st.success("Постер-задание добавлено")
        except ValueError as e:
            st.error(str(e))

st.divider()

st.subheader("Текущие задания")
questions = load_bank(bank_name, section=SECTION)
question_edit_key = f"question_edit_id_{bank_name}_{SECTION}"
if question_edit_key not in st.session_state:
    st.session_state[question_edit_key] = None

eid = st.session_state.get(question_edit_key)
if eid and questions:
    qe = next((q for q in questions if str(q.get("id")) == str(eid)), None)
    if qe is None:
        st.session_state[question_edit_key] = None
    else:
        st.markdown("#### Редактирование задания")
        st.caption(f"Тип: {qe.get('type', '?')}")
        t_val = st.text_area(
            "Текст задания",
            value=qe.get("text") or "",
            height=200,
            key=f"qedit_text_{bank_name}_{eid}",
        )
        ins_val: Optional[str] = None
        if qe.get("type") == "word_form":
            ins_val = st.text_area(
                "Инструкция",
                value=qe.get("instruction") or "",
                height=100,
                key=f"qedit_instr_{bank_name}_{eid}",
            )
        ec1, ec2 = st.columns(2)
        with ec1:
            if st.button("Сохранить изменения", type="primary", key=f"qedit_save_{bank_name}_{eid}"):
                if qe.get("type") == "word_form":
                    ok = update_question_fields(
                        bank_name, str(eid), SECTION, text=t_val, instruction=ins_val or ""
                    )
                else:
                    ok = update_question_fields(bank_name, str(eid), SECTION, text=t_val)
                if ok:
                    st.session_state[question_edit_key] = None
                    _admin_rerun()
                else:
                    st.error("Не удалось сохранить.")
        with ec2:
            if st.button("Отмена", key=f"qedit_cancel_{bank_name}_{eid}"):
                st.session_state[question_edit_key] = None
                _admin_rerun()
        st.divider()

if not questions:
    st.info("Пока нет заданий в этом разделе")
else:
    st.caption(
        "Список ниже — **как в тесте**: сначала задания с номером «№ в тесте» (меньше — раньше), "
        "потом без номера — в порядке строк в файле банка. **0** снимает явный номер. "
        "После правок нажмите «Сохранить нумерацию»."
    )
    questions_display = sort_questions_for_test(questions)
    for q in questions_display:
        qid = str(q.get("id") or "")
        init_o = parse_positive_test_order(q.get("test_order")) or 0
        cols = st.columns([1, 4, 1, 1])
        with cols[0]:
            st.number_input(
                "№ в тесте",
                min_value=0,
                max_value=999,
                value=init_o,
                key=f"qtestord_{bank_name}_{SECTION}_{qid}",
                help="Положительное число — явный порядок. 0 — без номера (как в файле после пронумерованных).",
            )
        with cols[1]:
            if q.get("type") == "mcq":
                opts = ", ".join([f"{o['key']}) {o['text']}" for o in q.get("options", [])])
                qt = markdown_preserve_newlines(q.get("text") or "")
                ck = q.get("correct_keys") or ([q.get("correct_key")] if q.get("correct_key") else [])
                ck_label = ", ".join(str(k).upper() for k in ck)
                multi_tag = " [несколько ответов]" if mcq_is_multi_select(q) else ""
                st.markdown(f"- [MCQ]{multi_tag} {qt} — {opts} (верные: {ck_label})")
            elif q.get("type") == "word_form":
                qt = markdown_preserve_newlines(q.get("text") or "")
                st.markdown(f"- [WORD_FORM] {qt} (правильный ответ: {q.get('answer')})")
            elif q.get("type") == "image_inputs":
                qt = markdown_preserve_newlines(q.get("text") or "")
                st.markdown(f"- [IMAGE_INPUTS] {qt} — {len(q.get('images', []))} изображений")
            elif q.get("type") == "ordering":
                qt = markdown_preserve_newlines(q.get("text") or "")
                st.markdown(f"- [ORDERING] {qt} — {len(q.get('items', []))} элементов")
            elif q.get("type") == "poster":
                qt = markdown_preserve_newlines(q.get("text") or "")
                st.markdown(f"- [POSTER] {qt} — {len(q.get('points', []))} точек, изображение: {q.get('image_url')}")
        with cols[2]:
            if st.button("Редактировать", key=f"edit_q_{bank_name}_{q.get('id')}"):
                st.session_state[question_edit_key] = q.get("id")
                _admin_rerun()
        with cols[3]:
            st.button(
                "Удалить",
                key=f"del_{bank_name}_{SECTION}_{qid}",
                on_click=_delete_question_cb,
                args=(bank_name, qid),
            )
    row_save, row_auto, _ = st.columns([2, 2.5, 2])
    with row_save:
        if st.button("Сохранить нумерацию", type="primary", key=f"save_test_orders_{bank_name}_{SECTION}"):
            orders = {}
            for qq in questions:
                qid_s = str(qq.get("id") or "")
                wkey = f"qtestord_{bank_name}_{SECTION}_{qid_s}"
                if wkey in st.session_state:
                    orders[qid_s] = coerce_order_field_int(st.session_state.get(wkey))
                else:
                    orders[qid_s] = parse_positive_test_order(qq.get("test_order")) or 0
            try:
                set_questions_test_orders(bank_name, SECTION, orders)
                st.success("Нумерация сохранена.")
                _admin_rerun()
            except ValueError as e:
                st.error(str(e))
    with row_auto:
        if st.button("Пронумеровать 1…n по порядку в файле", key=f"autonum_test_orders_{bank_name}_{SECTION}"):
            orders_auto = {str(q.get("id")): i + 1 for i, q in enumerate(questions)}
            set_questions_test_orders(bank_name, SECTION, orders_auto)
            st.success("Номера выставлены по текущему порядку в JSON.")
            _admin_rerun()

st.divider()

st.subheader("Теория модуля")
st.caption("Добавляйте блоки по кнопке '+'. Фото каждого блока вставляются сразу после текста этого блока.")

editor_count_key = f"theory_editor_count_{bank_name}_{SECTION}"
if editor_count_key not in st.session_state:
    st.session_state[editor_count_key] = 1

block_count = int(st.session_state.get(editor_count_key, 1))
block_contents = []
for i in range(block_count):
    st.markdown(f"**Добавьте теоретический блок {i + 1}**")
    text = st.text_area(f"Текст блока {i + 1}", height=140, key=f"theory_text_{bank_name}_{i}")
    images = st.file_uploader(
        f"Фото после блока {i + 1} (необязательно)",
        type=["png", "jpg", "jpeg", "gif"],
        accept_multiple_files=True,
        key=f"theory_images_{bank_name}_{i}",
    )
    block_contents.append({"text": text or "", "images": images or []})
    if st.button("＋ Добавить еще один блок", key=f"add_theory_block_after_{bank_name}_{i}", use_container_width=True):
        st.session_state[editor_count_key] = min(block_count + 1, 20)
        _admin_rerun()
    st.divider()

st.caption("Сначала заполните блоки, затем нажмите «Сохранить теорию».")
col_save, col_remove = st.columns([2, 1])
with col_save:
    if st.button("Сохранить теорию", type="primary", use_container_width=True):
        parts = []
        for block in block_contents:
            block_md = block.get("text") or ""
            image_items = block.get("images") or []
            if block_md.strip():
                parts.append(block_md)
            if image_items:
                for f in image_items:
                    rel = save_uploaded_theory_image(f, bank_name)
                    if rel:
                        parts.append(f"![{f.name}]({rel})")
        md_text = "\n\n".join([p for p in parts if str(p).strip()])
        if not md_text.strip():
            st.error("Добавьте хотя бы один текстовый блок или фотографию.")
        else:
            append_theory_block(bank_name, SECTION, md_text)
            st.success("Блок теории добавлен. Откройте модуль и нажмите лампочку, чтобы посмотреть.")
with col_remove:
    if st.button("− Убрать последний", use_container_width=True, disabled=block_count <= 1):
        st.session_state[editor_count_key] = max(1, block_count - 1)
        _admin_rerun()

if st.button("Удалить теорию", type="secondary", use_container_width=True):
    deleted = delete_theory_markdown(bank_name, SECTION)
    if deleted:
        st.success("Теория удалена.")
    else:
        st.info("Для этого модуля теории пока нет.")

st.markdown("### Текущая теория")
theory_blocks = load_theory_blocks(bank_name, SECTION)
theory_edit_idx_key = f"theory_edit_idx_{bank_name}_{SECTION}"
if theory_edit_idx_key not in st.session_state:
    st.session_state[theory_edit_idx_key] = None

ei = st.session_state.get(theory_edit_idx_key)
if ei is not None and theory_blocks and isinstance(ei, int) and 0 <= ei < len(theory_blocks):
    st.markdown(f"#### Редактирование блока {ei + 1}")
    edited_body = st.text_area(
        "Содержимое блока (Markdown)",
        value=theory_blocks[ei],
        height=320,
        key=f"theory_edit_ta_{bank_name}_{SECTION}_{ei}",
    )
    edit_imgs = st.file_uploader(
        "Добавить изображения в конец блока (необязательно)",
        type=["png", "jpg", "jpeg", "gif"],
        accept_multiple_files=True,
        key=f"theory_edit_img_{bank_name}_{SECTION}_{ei}",
    )
    ec1, ec2 = st.columns(2)
    with ec1:
        if st.button("Сохранить изменения", type="primary", key=f"theory_save_edit_{bank_name}_{ei}"):
            md_out = edited_body or ""
            if edit_imgs:
                for f in edit_imgs:
                    rel = save_uploaded_theory_image(f, bank_name)
                    if rel:
                        md_out += f"\n\n![{f.name}]({rel})\n"
            if not md_out.strip():
                st.error("Блок не может быть пустым.")
            else:
                ok = update_theory_block(bank_name, SECTION, ei, md_out)
                if ok:
                    st.session_state[theory_edit_idx_key] = None
                    _admin_rerun()
                else:
                    st.error("Не удалось сохранить блок.")
    with ec2:
        if st.button("Отмена", key=f"theory_cancel_edit_{bank_name}_{ei}"):
            st.session_state[theory_edit_idx_key] = None
            _admin_rerun()
    st.divider()

if not theory_blocks:
    st.info("Для этого модуля пока нет теоретических блоков.")
else:
    for i, block in enumerate(theory_blocks):
        cols = st.columns([5, 1, 1])
        with cols[0]:
            st.markdown(f"**Блок {i + 1}**")
            render_markdown_with_image_paths(block)
        with cols[1]:
            if st.button("Редактировать", key=f"edit_theory_block_{bank_name}_{i}"):
                st.session_state[theory_edit_idx_key] = i
                _admin_rerun()
        with cols[2]:
            if st.button("Удалить", key=f"del_theory_block_{bank_name}_{i}"):
                ok = delete_theory_block(bank_name, SECTION, i)
                if ok:
                    ei_old = st.session_state.get(theory_edit_idx_key)
                    if ei_old is not None:
                        if ei_old == i:
                            st.session_state[theory_edit_idx_key] = None
                        elif ei_old > i:
                            st.session_state[theory_edit_idx_key] = ei_old - 1
                    _admin_rerun()
