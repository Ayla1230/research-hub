"""A small PDF text reader, standard library only.

Enough of the format to read what Word, LaTeX and publishers produce, including Chinese: object streams,
Flate streams, page resources, and the ToUnicode maps that turn the font's glyph codes back into text.
It does not render, so reading order follows the content stream; scanned (image-only) PDFs have no text.
"""
from __future__ import annotations

import re
import zlib

_OBJ = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.S)
_REF = re.compile(rb"(\d+)\s+\d+\s+R")
_TOKEN = re.compile(
    rb"\((?:\\.|[^\\()])*\)"      # (literal string)
    rb"|<[0-9A-Fa-f\s]*>"         # <hex string>
    rb"|\[|\]"
    rb"|/[^\s/\[\]()<>]+"         # /Name
    rb"|[-+]?\d*\.?\d+"           # number
    rb"|[A-Za-z'\"*]+",           # operator
)
_ESC = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f", b"(": b"(", b")": b")", b"\\": b"\\"}


def _inflate(raw: bytes) -> bytes:
    for candidate in (raw, raw.rstrip(b"\r\n"), raw[:-1]):
        try:
            return zlib.decompress(candidate)
        except zlib.error:
            continue
    try:
        return zlib.decompressobj().decompress(raw)  # truncated stream: keep what can be read
    except zlib.error:
        return b""


class _Doc:
    def __init__(self, data: bytes):
        self.objects: dict[int, bytes] = {}
        for m in _OBJ.finditer(data):
            self.objects[int(m.group(1))] = m.group(3)
        for body in list(self.objects.values()):  # objects packed inside object streams (PDF 1.5+)
            if b"/ObjStm" not in body[:400]:
                continue
            head, stream = self.split(body)
            n, first = re.search(rb"/N\s+(\d+)", head), re.search(rb"/First\s+(\d+)", head)
            if not (n and first and stream):
                continue
            index = stream[: int(first.group(1))].split()
            for i in range(0, min(len(index), int(n.group(1)) * 2) - 1, 2):
                try:
                    num, offset = int(index[i]), int(index[i + 1])
                    end = int(index[i + 3]) if i + 3 < len(index) else len(stream)
                except ValueError:
                    break
                self.objects.setdefault(num, stream[int(first.group(1)) + offset: int(first.group(1)) + end])

    def split(self, body: bytes) -> tuple[bytes, bytes]:
        """(dictionary part, decoded stream) of an object."""
        m = re.search(rb"stream\r?\n", body)
        if not m:
            return body, b""
        head, raw = body[: m.start()], body[m.end():]
        end = raw.rfind(b"endstream")
        raw = raw[:end] if end >= 0 else raw
        if b"/FlateDecode" in head:
            raw = _inflate(raw)
        elif b"/Filter" in head:
            raw = b""  # image or unsupported filter
        return head, raw

    def get(self, ref: bytes | None) -> bytes:
        m = _REF.match(ref.strip()) if ref else None
        return self.objects.get(int(m.group(1)), b"") if m else b""

    def entry(self, head: bytes, key: bytes) -> bytes:
        """Value of /Key in a dictionary: the inline << >> dictionary, or the object a reference points to."""
        m = re.search(rb"/" + key + rb"\s*(<<|\d+\s+\d+\s+R)", head)
        if not m:
            return b""
        if m.group(1) != b"<<":
            return self.get(m.group(1))
        depth, i = 0, m.start(1)
        while i < len(head) - 1:
            if head[i:i + 2] == b"<<":
                depth += 1
                i += 2
            elif head[i:i + 2] == b">>":
                depth -= 1
                i += 2
                if depth == 0:
                    return head[m.start(1): i]
            else:
                i += 1
        return head[m.start(1):]


def _cmap(stream: bytes) -> tuple[dict[int, str], int]:
    """ToUnicode map: glyph code → text, and the code width in bytes."""
    table: dict[int, str] = {}
    width = 1
    for m in re.finditer(rb"begincodespacerange(.*?)endcodespacerange", stream, re.S):
        for lo in re.findall(rb"<([0-9A-Fa-f]+)>", m.group(1)):
            width = max(width, len(lo) // 2)
    text = lambda h: bytes.fromhex(h.decode()).decode("utf-16-be", errors="ignore")  # noqa: E731
    for m in re.finditer(rb"beginbfchar(.*?)endbfchar", stream, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", m.group(1)):
            if len(dst) % 4 == 0 and dst:
                table[int(src, 16)] = text(dst)
    for m in re.finditer(rb"beginbfrange(.*?)endbfrange", stream, re.S):
        for lo, hi, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]*>|\[[^\]]*\])", m.group(1)):
            a, b = int(lo, 16), int(hi, 16)
            if b - a > 70000:
                continue
            if dst.startswith(b"["):
                for i, item in enumerate(re.findall(rb"<([0-9A-Fa-f]+)>", dst)):
                    if len(item) % 4 == 0:
                        table[a + i] = text(item)
            else:
                h = dst.strip(b"<>")
                if not h or len(h) % 4:
                    continue
                base = int(h[-4:], 16)
                prefix = text(h[:-4]) if len(h) > 4 else ""
                for i in range(b - a + 1):
                    if base + i <= 0xFFFF:
                        table[a + i] = prefix + chr(base + i)
    return table, width


def _literal(token: bytes) -> bytes:
    body = token[1:-1]
    out, i = bytearray(), 0
    while i < len(body):
        c = body[i:i + 1]
        if c != b"\\":
            out += c
            i += 1
            continue
        nxt = body[i + 1:i + 2]
        if nxt in _ESC:
            out += _ESC[nxt]
            i += 2
        elif nxt.isdigit():
            j = i + 1
            while j < min(i + 4, len(body)) and body[j:j + 1].isdigit():
                j += 1
            out.append(int(body[i + 1:j], 8) & 0xFF)
            i = j
        elif nxt in (b"\n", b"\r"):
            i += 2
        else:
            i += 1
    return bytes(out)


def _decode(raw: bytes, font) -> str:
    if not font or not font[0]:
        return raw.decode("latin-1", errors="replace")
    table, width = font
    out = []
    for i in range(0, len(raw) - width + 1, width):
        code = int.from_bytes(raw[i:i + width], "big")
        out.append(table.get(code, chr(code) if width == 1 and 32 <= code < 256 else ""))
    return "".join(out).replace("\ufffd", "")


def _page_text(content: bytes, fonts: dict[bytes, tuple]) -> str:
    out: list[str] = []
    stack: list[bytes] = []
    font = None
    in_array = False
    size = 12.0
    last_y = None
    for token in _TOKEN.findall(content):
        first = token[:1]
        if first in b"(<" or first == b"/" or first.isdigit() or first in b"-+.":
            stack.append(token)
            continue
        if token == b"[":
            in_array = True
            stack.append(token)
            continue
        if token == b"]":
            in_array = False
            stack.append(token)
            continue
        op = token
        if op == b"Tf" and len(stack) >= 2:
            font = fonts.get(stack[-2][1:])
            try:
                size = float(stack[-1]) or size
            except ValueError:
                pass
        elif op in (b"Tj", b"'", b'"') and stack:
            if op != b"Tj":
                out.append("\n")
            s = stack[-1]
            raw = _literal(s) if s[:1] == b"(" else bytes.fromhex(re.sub(rb"\s", b"", s[1:-1]).decode() + ("0" if len(re.sub(rb"\s", b"", s[1:-1])) % 2 else ""))
            out.append(_decode(raw, font))
        elif op == b"TJ":
            start = max((i for i, t in enumerate(stack) if t == b"["), default=0)
            for item in stack[start + 1:]:
                if item[:1] == b"(":
                    out.append(_decode(_literal(item), font))
                elif item[:1] == b"<":
                    h = re.sub(rb"\s", b"", item[1:-1])
                    out.append(_decode(bytes.fromhex((h + (b"0" if len(h) % 2 else b"")).decode()), font))
                else:
                    try:
                        if float(item) < -200:  # a wide gap inside a line is a space
                            out.append(" ")
                    except ValueError:
                        pass
        elif op in (b"Td", b"TD") and len(stack) >= 2:
            try:
                dy, dx = float(stack[-1]), float(stack[-2])
            except ValueError:
                dy = dx = 0.0
            if abs(dy) > 0.5:
                out.append("\n")
                last_y = None
            elif dx > size * 0.25 and out and not out[-1].endswith((" ", "\n")):
                out.append(" ")
        elif op == b"Tm" and len(stack) >= 6:
            try:
                y = float(stack[-1])
            except ValueError:
                y = None
            # Word writes every run with its own Tm: only a new baseline starts a new line
            if y is None or last_y is None or abs(y - last_y) > 1.0:
                if out and not out[-1].endswith("\n"):
                    out.append("\n")
            last_y = y
        elif op == b"T*":
            if out and not out[-1].endswith("\n"):
                out.append("\n")
        if not in_array:
            stack.clear()
    return "".join(out)


def extract(data: bytes) -> str:
    """Text of a PDF, page by page. Returns "" when nothing readable was found."""
    doc = _Doc(data)
    font_cache: dict[int, tuple] = {}

    def fonts_of(resources: bytes) -> dict[bytes, tuple]:
        fdict = doc.entry(resources, b"Font")
        found = {}
        for name, num in re.findall(rb"/([^\s/\[\]()<>]+)\s+(\d+)\s+\d+\s+R", fdict):
            n = int(num)
            if n not in font_cache:
                body = doc.objects.get(n, b"")
                ref = re.search(rb"/ToUnicode\s+(\d+\s+\d+\s+R)", body)
                table, width = _cmap(doc.split(doc.get(ref.group(1)))[1]) if ref else ({}, 1)
                if not re.search(rb"/Subtype\s*/Type0", body):
                    width = 1  # simple fonts use one byte per glyph whatever the map's code space says
                font_cache[n] = (table, width)
            found[name] = font_cache[n]
        return found

    pages = []
    for num in sorted(doc.objects):
        body = doc.objects[num]
        head = body[:6000]
        if not re.search(rb"/Type\s*/Page\b(?!s)", head):
            continue
        resources = doc.entry(head, b"Resources")
        if not resources:  # inherited from the parent Pages node
            parent = doc.get((re.search(rb"/Parent\s+(\d+\s+\d+\s+R)", head) or [None, None])[1])
            resources = doc.entry(parent, b"Resources")
        fonts = fonts_of(resources)
        contents = re.search(rb"/Contents\s*(\[[^\]]*\]|\d+\s+\d+\s+R)", head)
        if not contents:
            continue
        stream = b"\n".join(doc.split(doc.objects.get(int(n), b""))[1] for n in _REF.findall(contents.group(1)))
        text = _page_text(stream, fonts)
        if text.strip():
            pages.append(text)
    text = "\n\n".join(pages)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", unwrap(text)).strip()


def unwrap(text: str) -> str:
    """Join lines that were only broken by the page width, so sentences read whole again.
    Short lines (titles, headings, list items) and lines that end a sentence are left alone."""
    lines = text.split("\n")
    widths = sorted(len(ln) for ln in lines if len(ln) >= 12)
    full = widths[int(len(widths) * 0.8)] if widths else 0  # a typical full line
    out: list[str] = []
    for line in lines:
        prev = out[-1] if out else ""
        cjk = bool(re.search(r"[\u3400-\u9fff]", prev[-3:] or ""))
        long_enough = len(prev) >= max(12, full * (0.72 if cjk else 0.6))
        if prev and line.strip() and long_enough and not re.search(r"[。！？!?；;：:]$|\.$", prev.rstrip()) and not re.match(r"\s*(?:第[一二三四五六七八九十]+[章節]|\d+[.、)]|[•●■\-])", line):
            glue = "" if cjk and re.match(r"[\u3400-\u9fff，。、；：（）「」]", line.lstrip()[:1] or "") else " "
            if prev.endswith("-") and glue == " " and re.match(r"[a-z]", line.lstrip()[:1] or ""):
                out[-1] = prev[:-1] + line.lstrip()  # hyphenated word split across lines
            else:
                out[-1] = prev.rstrip() + glue + line.lstrip()
        else:
            out.append(line)
    return "\n".join(out)
