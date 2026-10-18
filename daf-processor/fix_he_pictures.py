#!/usr/bin/env python3
"""Repair the mirrored pictures in Hebrew outlines (hebrew_pass.py output). No API.

hebrew_pass mirrors a picture by wrapping its drawing in <g transform="matrix(-1 0 0 1 W 0)">
and placing each label outside the group at W - x with text-anchor start/end swapped. Two faults:

1. The ✓ / ✗ marks (#mark-ok, #mark-no) went inside the mirrored group, so the check mark came out
   reversed. A check mark reads the same in Hebrew. They are moved out of the group, to the
   mirrored position (W - x - width), drawn unmirrored.
2. The model also set direction="rtl" on the labels it had already swapped. With direction rtl,
   text-anchor start/end refer to the right/left edge, so the swap was undone twice over and labels
   ran the wrong way off their anchor (into the marks, or off the picture). The anchors are flipped
   back to match rtl (a missing anchor means start, so it becomes end).

    venv/bin/python fix_he_pictures.py [--dry-run]     # every outline/results/*/04_outline_he.json
"""
import argparse
import glob
import json
import re
import shutil
from pathlib import Path

MIRROR = re.compile(r"<g\s+transform\s*=\s*['\"]matrix\(\s*-1\s+0\s+0\s+1\s+([\d.]+)\s+0\s*\)['\"]\s*>")
MARK = re.compile(r"<use\b[^>]*href\s*=\s*['\"]#mark-(?:ok|no)['\"][^>]*/>")
FLIP = {"start": "end", "end": "start"}


def group_span(svg, m):
    """(start, end) of the group opened at m, including its closing tag (groups may nest)."""
    depth, i = 1, m.end()
    for t in re.finditer(r"<g\b[^>]*?(/?)>|</g>", svg[i:]):
        if t.group(0) == "</g>":
            depth -= 1
            if depth == 0:
                return m.start(), i + t.end()
        elif not t.group(1):
            depth += 1
    return None


def attr(tag, name):
    a = re.search(rf"\b{name}\s*=\s*['\"]([^'\"]*)['\"]", tag)
    return a.group(1) if a else None


def unmirror_marks(svg):
    m = MIRROR.search(svg)
    if not m:
        return svg, 0
    span = group_span(svg, m)
    if not span:
        return svg, 0
    W = float(m.group(1))
    s, e = span
    group = svg[s:e]
    marks = MARK.findall(group)
    if not marks:
        return svg, 0
    moved = []
    for u in marks:
        x, w = float(attr(u, "x") or 0), float(attr(u, "width") or 0)
        nx = W - x - w
        moved.append(re.sub(r"\bx\s*=\s*['\"][^'\"]*['\"]", f"x='{nx:g}'", u, count=1))
    group = MARK.sub("", group)
    return svg[:s] + group + "".join(moved) + svg[e:], len(marks)


def fix_anchors(svg):
    n = 0

    def fix(m):
        nonlocal n
        tag = m.group(0)
        if attr(tag, "direction") != "rtl":
            return tag
        a = attr(tag, "text-anchor") or "start"
        if a not in FLIP:
            return tag
        n += 1
        if attr(tag, "text-anchor"):
            return re.sub(r"\btext-anchor\s*=\s*['\"][^'\"]*['\"]", f"text-anchor='{FLIP[a]}'", tag)
        return tag[:-1] + f" text-anchor='{FLIP[a]}'>"

    return re.sub(r"<text\b[^>]*>", fix, svg), n


def fix_svg(svg):
    svg, marks = unmirror_marks(svg)
    # mirrored or not, the model wrote its anchors in the left-to-right sense
    svg, anchors = fix_anchors(svg)
    return svg, marks, anchors


def fix_outline(o):
    tm = ta = 0

    def walk(ns):
        nonlocal tm, ta
        for n in ns or []:
            il = n.get("illustration")
            if isinstance(il, dict) and il.get("svg"):
                il["svg"], m, a = fix_svg(il["svg"])
                tm += m
                ta += a
            walk(n.get("children"))

    walk(o.get("sections"))
    return tm, ta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for f in sorted(glob.glob(str(Path(__file__).parent / "outline/results/*/04_outline_he.json"))):
        p = Path(f)
        o = json.loads(p.read_text(encoding="utf-8"))
        if o.get("_pictures_fixed"):
            continue
        tm, ta = fix_outline(o)
        print(f"{p.parent.name:16s} marks {tm:3d}  labels {ta:3d}")
        if args.dry_run:
            continue
        b = p.with_name(p.stem + ".before_picfix.json")
        if not b.exists():
            shutil.copy2(p, b)
        o["_pictures_fixed"] = True
        p.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
