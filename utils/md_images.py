"""Markdown + local / remote images for Streamlit."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Optional

import streamlit as st

_IMG_LINK = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _resolve_local_image_path(src: str) -> Path:
    p = Path(src.strip())
    if p.is_absolute():
        return p.expanduser()
    root = Path(__file__).resolve().parent.parent
    return (root / p).expanduser()


def render_inline_image(path_or_url: str) -> None:
    src = (path_or_url or "").strip()
    if src.startswith("http://") or src.startswith("https://"):
        st.markdown(f"<img src='{src}' style='width:100%; border-radius:8px;' />", unsafe_allow_html=True)
        return
    try:
        p = _resolve_local_image_path(src)
        data = p.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        ext = p.suffix.lower()
        mime = "image/png" if ext not in [".jpg", ".jpeg", ".gif"] else ("image/jpeg" if ext in [".jpg", ".jpeg"] else "image/gif")
        st.markdown(f"<img src='data:{mime};base64,{b64}' style='width:100%; border-radius:8px;' />", unsafe_allow_html=True)
    except Exception:
        st.caption("[image]")


def render_markdown_with_image_paths(markdown: str) -> None:
    """Render markdown; embed local image paths like banks/media/x.png via render_inline_image."""
    text = markdown or ""
    if not text.strip():
        return
    pos = 0
    for m in _IMG_LINK.finditer(text):
        before = text[pos : m.start()]
        if before:
            st.markdown(before, unsafe_allow_html=False)
        alt, raw_url = m.group(1), (m.group(2) or "").strip().strip("\"'")
        if raw_url.startswith(("http://", "https://", "data:")):
            st.markdown(f"![{alt}]({raw_url})", unsafe_allow_html=False)
        else:
            render_inline_image(raw_url)
        pos = m.end()
    tail = text[pos:]
    if tail:
        st.markdown(tail, unsafe_allow_html=False)


def save_uploaded_theory_image(uploaded, bank_name: str, media_dir: str = "banks/media") -> Optional[str]:
    """Write uploaded image to banks/media; return posix path banks/media/... for markdown."""
    import uuid

    root = Path(__file__).resolve().parent.parent
    out_dir = root / media_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(getattr(uploaded, "name", "") or "").suffix or ".png"
    fname = f"theory_{bank_name}_{uuid.uuid4().hex}{ext}"
    path = out_dir / fname
    try:
        data = uploaded.getbuffer() if hasattr(uploaded, "getbuffer") else uploaded.read()
        path.write_bytes(data)
        return f"{media_dir}/{fname}".replace("\\", "/")
    except Exception:
        return None


def markdown_preserve_newlines(text: Optional[str]) -> str:
    """Turn newlines into Markdown hard breaks (two spaces + newline) so blank lines survive st.markdown."""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if "\n" not in raw:
        return raw
    return raw.replace("\n", "  \n")
