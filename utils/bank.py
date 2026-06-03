import json
import html
import uuid
import re
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

_REPO_BANKS_DIR = Path(__file__).resolve().parent.parent / "banks"
_BANKS_ROOT: Optional[Path] = None

# Legacy name: repo path (may be read-only on Streamlit Cloud).
BANKS_DIR = _REPO_BANKS_DIR


def get_banks_root() -> Path:
    """Writable banks directory (repo locally, /tmp overlay on read-only deploys)."""
    global _BANKS_ROOT
    if _BANKS_ROOT is not None:
        return _BANKS_ROOT
    try:
        _REPO_BANKS_DIR.mkdir(parents=True, exist_ok=True)
        probe = _REPO_BANKS_DIR / ".write_probe"
        probe.write_text("1", encoding="utf-8")
        probe.unlink(missing_ok=True)
        _BANKS_ROOT = _REPO_BANKS_DIR
    except OSError:
        overlay = Path("/tmp/medengl_banks")
        if not overlay.exists():
            shutil.copytree(_REPO_BANKS_DIR, overlay, dirs_exist_ok=True)
        _BANKS_ROOT = overlay
    return _BANKS_ROOT
THEORY_BLOCK_DELIMITER = "\n\n<!-- THEORY_BLOCK_DELIMITER -->\n\n"

BANK_NAMES = [f"bank{i}" for i in range(1, 9)]

_MODULE_TITLES = (
    "Research",
    "First Aid Kit",
    "Jobs",
    "Toxins",
)


def _numbered_module_label(index: int, title: str) -> str:
    """``1. Research`` — non-breaking space so the number is not clipped in narrow buttons."""
    return f"{index + 1}.\u00a0{title}"


MODULE_DISPLAY_NAMES = [
    _numbered_module_label(0, _MODULE_TITLES[0]),
    _numbered_module_label(1, _MODULE_TITLES[1]),
    _numbered_module_label(2, _MODULE_TITLES[2]),
    _numbered_module_label(3, _MODULE_TITLES[3]),
    "Module 5",
    "Module 6",
    "Module 7",
    "Module 8",
]


def module_display_name(bank_name: str, *, default: str = "") -> str:
    """Human title for a bank (e.g. ``bank1`` → ``1. Research``)."""
    if bank_name == "combined":
        return "Final Test"
    try:
        return MODULE_DISPLAY_NAMES[BANK_NAMES.index(bank_name)]
    except ValueError:
        return default or bank_name


def is_ephemeral_banks_storage() -> bool:
    """True when data is stored outside the project folder (e.g. Streamlit Cloud /tmp)."""
    return get_banks_root().resolve() != _REPO_BANKS_DIR.resolve()

# Сколько вопросов показывать в итоговом тесте по всем модулям (случайная выборка после дедупликации).
FINAL_TEST_QUESTION_LIMIT = 20

_MCQ_MULTI_TEXT_MARKERS = (
    "choose all",
    "select all",
    "all that are true",
    "all of the following",
    "choose all that",
)


def mcq_is_multi_select(q: Dict[str, Any]) -> bool:
    """Whether the student UI should allow selecting more than one MCQ option."""
    if q.get("allow_multiple"):
        return True
    keys = q.get("correct_keys") or []
    if len(keys) > 1:
        return True
    text = (q.get("text") or "").lower()
    return any(marker in text for marker in _MCQ_MULTI_TEXT_MARKERS)


def parse_positive_test_order(raw: object) -> Optional[int]:
    """``test_order`` from JSON or widgets: positive int, or ``None`` if missing / invalid / non-positive."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, float):
        if raw <= 0 or raw != int(raw):
            return None
        iv = int(raw)
        return iv if iv > 0 else None
    if isinstance(raw, str):
        try:
            v = int(raw.strip())
            return v if v > 0 else None
        except ValueError:
            return None
    return None


def coerce_order_field_int(raw: object) -> int:
    """Non-negative int for saving ``test_order`` (0 clears explicit order)."""
    if raw is None:
        return 0
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw if raw >= 0 else 0
    if isinstance(raw, float):
        iv = int(raw)
        return iv if iv >= 0 else 0
    if isinstance(raw, str):
        try:
            v = int(raw.strip())
            return v if v >= 0 else 0
        except ValueError:
            return 0
    return 0


def _bank_path(bank_name: str, section: Optional[str] = None) -> Path:
    """Return path to bank json file.

    If section is provided, use a subdirectory under BANKS_DIR to separate banks by section,
    e.g., banks/engineers/bank1.json.
    """
    if section:
        section_dir = get_banks_root() / section
        section_dir.mkdir(parents=True, exist_ok=True)
        return section_dir / f"{bank_name}.json"
    return get_banks_root() / f"{bank_name}.json"


def ensure_bank_exists(bank_name: str, section: Optional[str] = None) -> None:
    path = _bank_path(bank_name, section)
    if not path.exists():
        path.write_text("[]", encoding="utf-8")


def load_bank(bank_name: str, section: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_bank_exists(bank_name, section)
    path = _bank_path(bank_name, section)
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "[]")
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def save_bank(bank_name: str, questions: List[Dict[str, Any]], section: Optional[str] = None) -> None:
    path = _bank_path(bank_name, section)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Cannot write question bank {path}: {exc}") from exc


def add_mcq_question(
    bank_name: str,
    text: str,
    options: List[Dict[str, str]],
    correct_keys: List[str],
    section: Optional[str] = None,
    *,
    allow_multiple: bool = False,
) -> Dict[str, Any]:
    questions = load_bank(bank_name, section)
    norm_keys = [str(k).strip().lower() for k in correct_keys if str(k).strip()]
    norm_keys = list(dict.fromkeys(norm_keys))  # unique, keep order
    multi = allow_multiple or len(norm_keys) > 1 or mcq_is_multi_select({"text": text})
    new_q: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "type": "mcq",
        "text": text,
        "options": options,
        "correct_keys": norm_keys,
        "allow_multiple": multi,
    }
    if len(norm_keys) == 1 and not multi:
        new_q["correct_key"] = norm_keys[0]  # backward compatibility
    questions.append(new_q)
    save_bank(bank_name, questions, section)
    return new_q


def add_word_form_question(
    bank_name: str,
    text_with_blank: str,
    correct_form: str,
    section: Optional[str] = None,
    instruction_text: str = "",
) -> Dict[str, Any]:
    """Adds a case-insensitive word form question.

    The question expects a single-word answer that fills the blank. Comparison is case-insensitive.
    """
    questions = load_bank(bank_name, section)
    new_q = {
        "id": str(uuid.uuid4()),
        "type": "word_form",
        "text": text_with_blank,
        "answer": correct_form,
        "instruction": instruction_text,
    }
    questions.append(new_q)
    save_bank(bank_name, questions, section)
    return new_q


IMAGE_INPUTS_MIN = 3
IMAGE_INPUTS_MAX = 5


def add_image_inputs_question(
    bank_name: str,
    items: List[Dict[str, str]],
    section: Optional[str] = None,
    instruction_text: str = "",
) -> Dict[str, Any]:
    """Adds an image-inputs question with 3–5 images and expected answers per image.

    Each item must be of the form {"url": str, "answer": str}.
    Answers are compared case-insensitively in the UI logic.
    """
    if len(items) < IMAGE_INPUTS_MIN or len(items) > IMAGE_INPUTS_MAX:
        raise ValueError(f"image_inputs questions must have {IMAGE_INPUTS_MIN}-{IMAGE_INPUTS_MAX} items")
    questions = load_bank(bank_name, section)
    new_q = {
        "id": str(uuid.uuid4()),
        "type": "image_inputs",
        "text": instruction_text,
        "images": items,
    }
    questions.append(new_q)
    save_bank(bank_name, questions, section)
    return new_q


POSTER_POINT_COUNT_MIN = 2
POSTER_POINT_COUNT_MAX = 11
POSTER_POINT_SLOTS = 11


def add_poster_question(
    bank_name: str,
    image_url: str,
    points: List[Dict[str, Any]],
    section: Optional[str] = None,
    instruction_text: str = "",
) -> Dict[str, Any]:
    """Adds a poster-presentation question.

    Expected structure for each point in ``points``:
      { "label": 1..n, "x": 0-100 (percent), "y": 0-100 (percent),
        "name": str, "description": str }

    ``x`` and ``y`` are stored as percentages relative to the image size.
    Between **POSTER_POINT_COUNT_MIN** and **POSTER_POINT_COUNT_MAX** points inclusive.
    Answers are compared case-insensitively in the UI logic.
    """
    n = len(points)
    if n < POSTER_POINT_COUNT_MIN or n > POSTER_POINT_COUNT_MAX:
        raise ValueError(f"poster questions must have between {POSTER_POINT_COUNT_MIN} and {POSTER_POINT_COUNT_MAX} points")
    # Basic normalization and validation
    cleaned: List[Dict[str, Any]] = []
    for idx, p in enumerate(points, start=1):
        label = int(p.get("label", idx))
        x = float(p.get("x", 0))
        y = float(p.get("y", 0))
        name = str(p.get("name", "")).strip()
        desc = str(p.get("description", "")).strip()
        if name == "":
            raise ValueError("Each poster point must include name")
        x = max(0.0, min(100.0, x))
        y = max(0.0, min(100.0, y))
        cleaned.append({"label": label, "x": x, "y": y, "name": name, "description": desc})

    questions = load_bank(bank_name, section)
    new_q = {
        "id": str(uuid.uuid4()),
        "type": "poster",
        "text": instruction_text,
        "image_url": image_url,
        "points": cleaned,
    }
    questions.append(new_q)
    save_bank(bank_name, questions, section)
    return new_q


def save_theory_markdown(bank_name: str, section: Optional[str], markdown_text: str) -> Path:
    """Save theory markdown for a module into banks/<section>/theory/<bank_name>.md.

    Returns the path to the saved file.
    """
    sec = section or "medical"
    theory_dir = get_banks_root() / sec / "theory"
    theory_dir.mkdir(parents=True, exist_ok=True)
    path = theory_dir / f"{bank_name}.md"
    path.write_text(markdown_text or "", encoding="utf-8")
    return path


def load_theory_markdown(bank_name: str, section: Optional[str]) -> str:
    """Load theory markdown for a module. Returns empty string if missing/unreadable."""
    sec = section or "medical"
    path = get_banks_root() / sec / "theory" / f"{bank_name}.md"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def theory_markdown_without_block_delimiters(raw: str) -> str:
    """Turn stored multi-block theory into one continuous document for readers."""
    if not raw:
        return ""
    s = raw.replace(THEORY_BLOCK_DELIMITER, "\n\n")
    s = s.replace("<!-- THEORY_BLOCK_DELIMITER -->", "")
    return s


def load_theory_blocks(bank_name: str, section: Optional[str]) -> List[str]:
    """Load theory blocks split by internal delimiter.

    For backward compatibility, plain text without delimiter is returned as one block.
    Preserves leading/trailing spaces and blank lines inside each block (only trims
    delimiter newlines at chunk edges).
    """
    text = load_theory_markdown(bank_name, section) or ""
    if not text.strip():
        return []
    if THEORY_BLOCK_DELIMITER not in text:
        return [text.strip("\n")]
    chunks: List[str] = []
    for chunk in text.split(THEORY_BLOCK_DELIMITER):
        if not chunk.strip():
            continue
        chunks.append(chunk.strip("\n"))
    return chunks


def append_theory_block(bank_name: str, section: Optional[str], markdown_block: str) -> Path:
    """Append one theory block while preserving older content."""
    new_block = markdown_block or ""
    existing_blocks = load_theory_blocks(bank_name, section)
    if new_block.strip():
        existing_blocks.append(new_block.strip("\n"))
    joined = THEORY_BLOCK_DELIMITER.join(existing_blocks)
    return save_theory_markdown(bank_name, section, joined)


def delete_theory_block(bank_name: str, section: Optional[str], block_index: int) -> bool:
    """Delete one theory block by index. Returns True on success."""
    blocks = load_theory_blocks(bank_name, section)
    if block_index < 0 or block_index >= len(blocks):
        return False
    blocks.pop(block_index)
    if not blocks:
        return delete_theory_markdown(bank_name, section)
    save_theory_markdown(bank_name, section, THEORY_BLOCK_DELIMITER.join(blocks))
    return True


def update_theory_block(bank_name: str, section: Optional[str], block_index: int, markdown_block: str) -> bool:
    """Replace one theory block by index. Returns False if index invalid or content empty."""
    blocks = load_theory_blocks(bank_name, section)
    if block_index < 0 or block_index >= len(blocks):
        return False
    new_block = markdown_block or ""
    if not new_block.strip():
        return False
    blocks[block_index] = new_block.strip("\n")
    save_theory_markdown(bank_name, section, THEORY_BLOCK_DELIMITER.join(blocks))
    return True


def delete_theory_markdown(bank_name: str, section: Optional[str]) -> bool:
    """Delete theory markdown for a module. Returns True if deleted."""
    sec = section or "medical"
    path = get_banks_root() / sec / "theory" / f"{bank_name}.md"
    if not path.exists():
        return False
    try:
        path.unlink()
        return True
    except Exception:
        return False


def sort_questions_for_test(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stable order for tests: explicit ``test_order`` (positive int) first, then unnumbered in file order.

    Questions without ``test_order`` or with non-positive values behave like unnumbered.
    """
    indexed = list(enumerate(questions))

    def sort_key(entry: Tuple[int, Dict[str, Any]]) -> Tuple[int, int, int]:
        file_idx, q = entry
        ov = parse_positive_test_order(q.get("test_order"))
        if ov is not None:
            return (0, ov, file_idx)
        return (1, file_idx, file_idx)

    indexed.sort(key=sort_key)
    return [q for _, q in indexed]


def set_questions_test_orders(
    bank_name: str,
    section: Optional[str],
    orders: Dict[str, int],
) -> None:
    """Set or clear ``test_order`` for questions in the bank. Value <= 0 removes the field."""
    questions = load_bank(bank_name, section)
    id_set = {str(q.get("id")) for q in questions}
    for k in orders:
        if str(k) not in id_set:
            raise ValueError(f"unknown question id: {k}")
    normalized = {str(k): int(v) for k, v in orders.items()}
    for q in questions:
        qid = str(q.get("id"))
        if qid not in normalized:
            continue
        v = normalized[qid]
        if v <= 0:
            q.pop("test_order", None)
        else:
            q["test_order"] = v
    save_bank(bank_name, questions, section)


def question_content_signature(q: Dict[str, Any]) -> str:
    """Stable fingerprint for de-duplicating questions with identical content across banks."""
    q_type = str(q.get("type"))
    if q_type == "mcq":
        opts = "|".join([str(o.get("key")) + ":" + str(o.get("text")) for o in q.get("options", [])])
        return f"mcq::{q.get('text', '')}::{opts}"
    if q_type == "word_form":
        return f"word::{q.get('text', '')}::{q.get('answer', '')}"
    if q_type == "image_inputs":
        urls = "|".join([str(i.get("url")) for i in q.get("images", [])])
        return f"img::{q.get('text', '')}::{urls}"
    if q_type == "ordering":
        items = "|".join([str(i) for i in q.get("items", [])])
        return f"ord::{q.get('text', '')}::{items}"
    if q_type == "poster":
        pts = ";".join(
            [f"{p.get('label')}:{p.get('x')}:{p.get('y')}:{p.get('name')}" for p in q.get("points", [])]
        )
        return f"poster::{q.get('image_url', '')}::{pts}"
    return f"other::{q.get('text', '')}"


def dedupe_questions(
    qs: List[Dict[str, Any]],
    max_unique: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """First occurrence wins. If ``max_unique`` is set, stop once that many unique questions are collected."""
    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for q in qs:
        sig = question_content_signature(q)
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(q)
        if max_unique is not None and len(unique) >= max_unique:
            break
    return unique


_ORDERING_LEADING_LABEL = re.compile(r"^[A-Z]\.\s*")


def normalize_ordering_item_text(s: str) -> str:
    """Remove a leading ``'A. '``-style marker so shuffle letters are not duplicated on screen."""
    t = (s or "").strip()
    return _ORDERING_LEADING_LABEL.sub("", t, count=1)


def ordering_items_row_html(items: List[Any], shuffled_idx: List[int], letters: List[str]) -> str:
    """Single horizontal row (wraps): flex layout uses **inline** styles so Streamlit markdown still honors it."""
    row_style = (
        "display:flex;flex-direction:row;flex-wrap:wrap;align-items:stretch;"
        "gap:10px;margin:0 0 12px 0;width:100%;"
    )
    chip_style = (
        "flex:1 1 180px;min-width:140px;max-width:100%;box-sizing:border-box;"
        "border:1px solid #2a2a2a;border-radius:10px;padding:12px 16px;"
        "background:#3a3a3a;color:#ffffff;font-size:1.15rem;line-height:1.55;"
    )
    parts: List[str] = []
    for j, orig_i in enumerate(shuffled_idx):
        if j >= len(letters) or orig_i < 0 or orig_i >= len(items):
            continue
        letter = html.escape(letters[j])
        raw = items[orig_i]
        if not isinstance(raw, str):
            raw = str(raw)
        body_plain = normalize_ordering_item_text(raw)
        body = html.escape(" ".join(body_plain.split()))
        parts.append(f'<div style="{chip_style}"><strong>{letter}.</strong> {body}</div>')
    return f'<div style="{row_style}">{"".join(parts)}</div>'


def parse_pasted_mcq(pasted: str) -> Tuple[str, List[Dict[str, str]]]:
    s = pasted.strip()
    s = re.sub(r"^\s*\d+[\.)\-]\s*", "", s)
    s = re.sub(r"\s+", " ", s)
    parts = re.split(r"\s([a-zA-Z])\)\s", s)
    if len(parts) >= 3 and isinstance(parts[1], str) and len(parts[1]) == 1:
        question_text = parts[0].strip()
        options: List[Dict[str, str]] = []
        i = 1
        while i + 1 < len(parts):
            key = parts[i].lower()
            text = parts[i + 1].strip()
            options.append({"key": key, "text": text})
            i += 2
        return question_text, options
    lines = [ln.strip() for ln in pasted.splitlines() if ln.strip()]
    if not lines:
        return pasted.strip(), []
    question_text = lines[0]
    options = []
    for ln in lines[1:]:
        m = re.match(r"^([a-zA-Z])\)\s*(.+)$", ln)
        if m:
            options.append({"key": m.group(1).lower(), "text": m.group(2).strip()})
    return question_text, options


def get_random_questions_from_bank(bank_name: str, limit: Optional[int] = None, section: Optional[str] = None) -> List[Dict[str, Any]]:
    questions = sort_questions_for_test(load_bank(bank_name, section))
    if limit is not None:
        return questions[:limit]
    return questions


def get_random_questions_from_multiple(banks: List[str], limit: Optional[int] = None, section: Optional[str] = None) -> List[Dict[str, Any]]:
    entries: List[Tuple[int, int, Dict[str, Any]]] = []
    for bank_idx, b in enumerate(banks):
        for file_idx, q in enumerate(load_bank(b, section)):
            entries.append((bank_idx, file_idx, q))

    def sort_key(entry: Tuple[int, int, Dict[str, Any]]) -> Tuple[int, int, int, int]:
        bank_idx, file_idx, q = entry
        ov = parse_positive_test_order(q.get("test_order"))
        if ov is not None:
            return (0, ov, bank_idx, file_idx)
        return (1, bank_idx, file_idx, file_idx)

    entries.sort(key=sort_key)
    pool = [q for _, _, q in entries]
    if limit is not None:
        return pool[:limit]
    return pool


def update_question_fields(
    bank_name: str,
    question_id: str,
    section: Optional[str] = None,
    *,
    text: Optional[str] = None,
    instruction: Optional[str] = None,
) -> bool:
    """Update main text and (for word_form) instruction. Returns False if question not found."""
    questions = load_bank(bank_name, section)
    for q in questions:
        if str(q.get("id")) != str(question_id):
            continue
        if text is not None:
            q["text"] = text
        if instruction is not None and q.get("type") == "word_form":
            q["instruction"] = instruction
        save_bank(bank_name, questions, section)
        return True
    return False


def delete_question(bank_name: str, question_id: str, section: Optional[str] = None) -> bool:
    """Delete a question by id from the specified bank. Returns True if deleted."""
    target = str(question_id or "").strip()
    if not target:
        return False
    questions = load_bank(bank_name, section)
    new_questions = [q for q in questions if str(q.get("id") or "").strip() != target]
    if len(new_questions) == len(questions):
        return False
    save_bank(bank_name, new_questions, section)
    return True


def add_ordering_question(
    bank_name: str,
    items_in_order: List[str],
    section: Optional[str] = None,
    instruction_text: str = "",
    answer_letters: str = "",
) -> Dict[str, Any]:
    """Adds an ordering question where the user must arrange options in the correct order.

    items_in_order: list of strings representing the correct order (min 3 items).
    """
    items_clean = [
        normalize_ordering_item_text(s.strip())
        for s in items_in_order
        if str(s).strip()
    ]
    items_clean = [x for x in items_clean if x.strip()]
    if len(items_clean) < 3:
        raise ValueError("ordering questions must have at least 3 items")
    questions = load_bank(bank_name, section)
    new_q: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "type": "ordering",
        "text": instruction_text,
        "items": items_clean,
    }
    if answer_letters.strip():
        new_q["answer_letters"] = str(answer_letters).strip().upper()
    questions.append(new_q)
    save_bank(bank_name, questions, section)
    return new_q


def _communicative_path(bank_name: str, section: Optional[str] = None) -> Path:
    sec = section or "medical"
    comm_dir = get_banks_root() / sec / "communicative"
    comm_dir.mkdir(parents=True, exist_ok=True)
    return comm_dir / f"{bank_name}.json"


def load_communicative_tasks(bank_name: str, section: Optional[str] = None) -> List[Dict[str, Any]]:
    path = _communicative_path(bank_name, section)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "[]")
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def save_communicative_tasks(
    bank_name: str,
    tasks: List[Dict[str, Any]],
    section: Optional[str] = None,
) -> None:
    path = _communicative_path(bank_name, section)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Cannot write communicative tasks {path}: {exc}") from exc


def add_communicative_task(
    bank_name: str,
    text: str,
    section: Optional[str] = None,
) -> Dict[str, Any]:
    tasks = load_communicative_tasks(bank_name, section)
    new_task: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "text": (text or "").strip(),
    }
    tasks.append(new_task)
    save_communicative_tasks(bank_name, tasks, section)
    return new_task


def delete_communicative_task(
    bank_name: str,
    task_id: str,
    section: Optional[str] = None,
) -> bool:
    target = str(task_id or "").strip()
    if not target:
        return False
    tasks = load_communicative_tasks(bank_name, section)
    new_tasks = [t for t in tasks if str(t.get("id") or "").strip() != target]
    if len(new_tasks) == len(tasks):
        return False
    save_communicative_tasks(bank_name, new_tasks, section)
    return True
