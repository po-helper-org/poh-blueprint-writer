#!/usr/bin/env python3
"""Упрощённый экран истории — файл SVG из строки таблицы «Экраны» документа «История».

Картинки экранов лежат в проекте Backlog.md файлами: `backlog/assets/screens/<ID>.svg`. Их пишет
`bft-backlog-build.py` из текстового описания («Состав»), страница карты и документы экранов
берут их оттуда по пути. Свой макет вместо упрощённого — файл `<ID>.png` (`.jpg`, `.webp`)
рядом: тогда страница показывает его. Рисунок тот же, что `mockSVG` в page_kit.js
(страница истории до проекта Backlog.md).

Только стандартная библиотека.
"""
from __future__ import annotations

import html
from pathlib import Path

ASSETS = "assets/screens"              # от папки backlog/
OVERRIDE = (".png", ".jpg", ".jpeg", ".webp")
W, H, P = 150, 250, 11
IW = W - 2 * P
INK, GREY, OFFER = "#1f1f1f", "#9a958c", "#6b3fd4"
FONT = "Inter,-apple-system,Helvetica,Arial,sans-serif"


def _n(v: float) -> str:
    """Число как в JS-шаблоне: 75, 10.5 — без хвоста `.0`."""
    return str(int(v)) if float(v).is_integer() else f"{v:.2f}".rstrip("0")


def wrap(text: str, n: int) -> list[str]:
    out, cur = [], ""
    for w in str(text).split(" "):
        if len((cur + " " + w).strip()) > n:
            if cur:
                out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def _t(x, y, s, fs, fw=400, fill=INK, anchor="") -> str:
    a = f' text-anchor="{anchor}"' if anchor else ""
    return f'<text x="{_n(x)}" y="{_n(y)}" font-size="{_n(fs)}" font-weight="{fw}" fill="{fill}"{a}>{html.escape(str(s), quote=False)}</text>'


def svg(device: str, view: str, contour: str, elements: list, label: str = "") -> str:
    """SVG экрана 150×250: рамка устройства, элементы сверху вниз; альтернативный вид — красная рамка."""
    label = label or contour
    head = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W * 2}" height="{H * 2}" font-family="{FONT}" role="img" aria-label="{html.escape(label)}">'
    if view == "неизвестен":
        ls = wrap(contour, 16)
        body = (f'<rect x="1.5" y="1.5" width="{W - 3}" height="{H - 3}" rx="20" fill="#fdf3f2" stroke="#c0392b" stroke-width="1.6" stroke-dasharray="6 4"/>'
                f'<circle cx="{_n(W / 2)}" cy="{_n(H / 2 - 14)}" r="20" fill="#c0392b"/>' + _t(W / 2, H / 2 - 6, "?", 24, 800, "#fff", "middle")
                + "".join(_t(W / 2, H / 2 + 30 + i * 14, ln, 11, 600, "#c0392b", "middle") for i, ln in enumerate(ls))
                + _t(W / 2, H / 2 + 30 + len(ls) * 14, "не определён", 11, 600, "#c0392b", "middle"))
        return head + body + "</svg>\n"
    if device == "web":
        y = 26
        frame = (f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="10" fill="#fff" stroke="#2b2b2b" stroke-width="1.5"/>'
                 f'<path d="M1,11 a10,10 0 0 1 10,-10 h{W - 22} a10,10 0 0 1 10,10 v7 h-{W - 2}z" fill="#efede8"/>'
                 + "".join(f'<circle cx="{10 + i * 7}" cy="10" r="2.2" fill="#bdb8af"/>' for i in range(3)))
    elif device == "mail":
        y = 12
        frame = f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="10" fill="#fff" stroke="#2b2b2b" stroke-width="1.5"/>'
    elif device == "lock":
        y = 78
        frame = (f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="#e6e2db" stroke="#2b2b2b" stroke-width="1.5"/>'
                 f'<rect x="{_n(W / 2 - 20)}" y="7" width="40" height="7" rx="3.5" fill="#2b2b2b"/>' + _t(W / 2, 56, "09:41", 30, 300, "#555", "middle"))
    else:
        y = 24
        frame = (f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="#fff" stroke="#2b2b2b" stroke-width="1.5"/>'
                 f'<rect x="{_n(W / 2 - 20)}" y="7" width="40" height="7" rx="3.5" fill="#2b2b2b"/>')
    out = []
    for it in elements:
        k = it[0]
        if k == "from":
            out.append(f'<path d="M{P},{y} h18 v12 h-18z M{P},{y} l9,7 l9,-7" fill="none" stroke="{GREY}" stroke-width="1.3"/>' + _t(P + 24, y + 10, it[1], 10, 600, GREY))
            y += 22
        elif k == "hdr":
            if it[1].startswith("✓ "):
                out.append(f'<circle cx="{P + 7}" cy="{y + 7}" r="7" fill="{INK}"/><path d="M{_n(P + 3.5)},{y + 7} l2.5,2.5 l4.5,-5" fill="none" stroke="#fff" stroke-width="1.8"/>'
                           + _t(P + 19, y + 11.5, it[1][2:], 12, 700))
            else:
                out.append(_t(P, y + 11.5, it[1], 12, 700))
            y += 22
        elif k == "text":
            for ln in wrap(it[1], 22):
                out.append(_t(P, y + 11, ln, 10.5, 400, GREY))
                y += 13
            y += 5
        elif k == "offer":
            ls = wrap(it[1], 13)
            h = len(ls) * 16 + 16
            out.append(f'<rect x="{P}" y="{y}" width="{IW}" height="{h}" rx="9" fill="{OFFER}"/>' + "".join(_t(P + 10, y + 20 + i * 16, ln, 13, 800, "#fff") for i, ln in enumerate(ls)))
            y += h + 9
        elif k in ("cta", "cta2"):
            fs = 9.5 if len(it[1]) > 16 else 11
            fill, color = (INK, "#fff") if k == "cta" else ("#fff", INK)
            out.append(f'<rect x="{P}" y="{y}" width="{IW}" height="26" rx="13" fill="{fill}" stroke="{INK}" stroke-width="1.2"/>' + _t(W / 2, y + 17, it[1], fs, 700, color, "middle"))
            y += 32
        elif k == "link":
            out.append(_t(P, y + 12, it[1], 11, 700) + f'<line x1="{P}" y1="{y + 15}" x2="{P + min(IW, len(it[1]) * 6)}" y2="{y + 15}" stroke="{INK}"/>')
            y += 22
        elif k == "tiles":
            tw = (IW - 8) / 2
            for i in range(2):
                x = P + i * (tw + 8)
                out.append(f'<rect x="{_n(x)}" y="{y}" width="{_n(tw)}" height="58" rx="7" fill="#fff" stroke="#d6d2ca"/>'
                           f'<rect x="{_n(x + 5)}" y="{y + 5}" width="{_n(tw - 10)}" height="24" rx="4" fill="#ece9e3"/>'
                           f'<rect x="{_n(x + 5)}" y="{y + 35}" width="{_n(tw - 22)}" height="6" rx="3" fill="#cfcac0"/>'
                           f'<rect x="{_n(x + 5)}" y="{y + 46}" width="{_n(tw - 34)}" height="5" rx="2.5" fill="#e3dfd8"/>'
                           f'<rect x="{_n(x + tw - 27)}" y="{y + 8}" width="22" height="13" rx="6.5" fill="{OFFER}"/>')
            y += 66
        elif k in ("rows", "rowsOffer"):
            for _ in range(int(it[1])):
                out.append(f'<rect x="{P}" y="{y}" width="26" height="26" rx="5" fill="#ece9e3"/><rect x="{P + 33}" y="{y + 5}" width="58" height="6" rx="3" fill="#cfcac0"/>'
                           f'<rect x="{P + 33}" y="{y + 16}" width="40" height="5" rx="2.5" fill="#e3dfd8"/>')
                if k == "rowsOffer":
                    out.append(f'<rect x="{W - P - 28}" y="{y + 6}" width="28" height="14" rx="7" fill="{OFFER}"/>')
                y += 34
        elif k == "chips":
            x = P
            for c in it[1]:
                w = len(c) * 6 + 14
                if x + w > W - P:
                    continue
                out.append(f'<rect x="{x}" y="{y}" width="{w}" height="20" rx="10" fill="#fff" stroke="#9a958c"/>' + _t(x + 7, y + 14, c, 10, 600))
                x += w + 5
            y += 30
        elif k == "kv":
            out.append(_t(P, y + 12, it[1], 10.5, 400, GREY) + _t(W - P, y + 12, it[2], 11, 700, INK, "end") + f'<line x1="{P}" y1="{y + 19}" x2="{W - P}" y2="{y + 19}" stroke="#eee"/>')
            y += 24
        elif k == "img":
            out.append(f'<rect x="{P}" y="{y}" width="{IW}" height="56" rx="7" fill="#ece9e3"/><path d="M{P + 20},{y + 44} l18,-20 l14,14 l10,-9 l18,15z" fill="#d6d1c8"/>')
            y += 64
        elif k == "camera":
            out.append(f'<rect x="{P}" y="{y}" width="{IW}" height="112" rx="8" fill="#2b2b2b"/>')
            for x, yy, dx, dy in ((P + 10, y + 10, 1, 1), (W - P - 10, y + 10, -1, 1), (P + 10, y + 102, 1, -1), (W - P - 10, y + 102, -1, -1)):
                out.append(f'<path d="M{x},{yy + 14 * dy} V{yy} H{x + 14 * dx}" fill="none" stroke="#fff" stroke-width="2.4"/>')
            for i in range(20):
                out.append(f'<rect x="{_n(P + 28 + i * 4.3)}" y="{y + 38}" width="{1.4 if i % 3 else 2.8}" height="36" fill="#fff"/>')
            y += 120
        elif k in ("ok", "no"):
            cx, cy = W / 2, y + 30
            col = "#2f6b2a" if k == "ok" else "#c0392b"
            out.append(f'<circle cx="{_n(cx)}" cy="{cy}" r="24" fill="{col}"/>')
            if k == "ok":
                out.append(f'<path d="M{_n(cx - 11)},{cy} l8,8 l14,-15" fill="none" stroke="#fff" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>')
            else:
                out.append(f'<path d="M{_n(cx - 9)},{cy - 9} l18,18 M{_n(cx + 9)},{cy - 9} l-18,18" stroke="#fff" stroke-width="3.4" stroke-linecap="round"/>')
            y += 64
            out.append(_t(cx, y + 6, it[1], 14, 800, INK if k == "ok" else "#c0392b", "middle"))
            y += 22
        elif k == "barcode":
            out.append(f'<rect x="{P}" y="{y}" width="{IW}" height="70" rx="8" fill="#fff" stroke="#d6d2ca"/>')
            for i in range(24):
                out.append(f'<rect x="{_n(P + 14 + i * 4.6)}" y="{y + 12}" width="{1.5 if i % 3 else 3}" height="46" fill="{INK}"/>')
            y += 80
        elif k == "notif":
            tl, ls = wrap(it[2], 17), wrap(it[3], 20)
            h = 34 + len(tl) * 15 + len(ls) * 13
            out.append(f'<rect x="{P - 3}" y="{y}" width="{IW + 6}" height="{h}" rx="12" fill="#fff"/><rect x="{P + 5}" y="{y + 8}" width="16" height="16" rx="4" fill="{OFFER}"/>'
                       + _t(P + 26, y + 20, it[1], 9.5, 600, GREY)
                       + "".join(_t(P + 5, y + 42 + i * 15, ln, 11.5, 800) for i, ln in enumerate(tl))
                       + "".join(_t(P + 5, y + 42 + len(tl) * 15 + i * 13, ln, 10.5, 400, "#444") for i, ln in enumerate(ls)))
            y += h + 10
    alt = ""
    if view == "альтернативный":
        alt = f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{10 if device in ("web", "mail") else 22}" fill="none" stroke="#c0392b" stroke-width="2.2"/>'
    return head + frame + "".join(out) + alt + "</svg>\n"


def image_of(bdir: Path, sid: str) -> str:
    """Картинка экрана от папки backlog/: свой макет, если лежит рядом, иначе упрощённый SVG."""
    for ext in OVERRIDE:
        if (bdir / ASSETS / f"{sid}{ext}").is_file():
            return f"{ASSETS}/{sid}{ext}"
    return f"{ASSETS}/{sid}.svg"


def sync(bdir: Path, screens: list, write: bool) -> list[str]:
    """SVG экранов из «Истории». Возвращает ID с устаревшим или пропавшим файлом; write — переписать.
    Лишние `<ID>.svg` экранов, которых в истории уже нет, удаляются (свои макеты .png не трогаем)."""
    stale = []
    d = bdir / ASSETS
    want = {sc.id: svg(sc.device, sc.view, sc.contour, sc.elements) for sc in screens}
    for sid, text in want.items():
        f = d / f"{sid}.svg"
        if f.is_file() and f.read_text(encoding="utf-8") == text:
            continue
        stale.append(sid)
        if write:
            d.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
    for f in sorted(d.glob("*.svg")) if d.is_dir() else []:
        if f.stem not in want:
            stale.append(f.stem)
            if write:
                f.unlink()
    return stale
