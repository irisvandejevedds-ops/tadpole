"""A small, safe Markdown renderer for the reference documents: headings, paragraphs, lists, tables, quotes, rules, bold, italic, code and links.
Everything is escaped first, so a document can never inject markup."""
import re
from html import escape

LINK = re.compile(r"\[([^\]]+)\]\(((?:https?://|/|#)[^)\s]*)\)")
WIKI = re.compile(r"!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def inline(s):
    s = escape(s, quote=False)
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"
    s = re.sub(r"`([^`]+)`", keep, s)
    s = WIKI.sub(lambda m: m.group(2) or m.group(1), s)
    s = LINK.sub(lambda m: f'<a href="{m.group(2)}" rel="noreferrer">{m.group(1)}</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<em>\1</em>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", s)


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render(md):
    lines = (md or "").replace("\r\n", "\n").split("\n")
    out, i, para = [], 0, []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            flush(); i += 1
        elif s.startswith("```"):
            flush(); i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            i += 1
            out.append("<pre>" + escape("\n".join(code), quote=False) + "</pre>")
        elif re.match(r"#{1,6}\s", s):
            flush()
            n = len(s) - len(s.lstrip("#"))
            out.append(f"<h{min(n + 1, 6)}>{inline(s[n:].strip())}</h{min(n + 1, 6)}>"); i += 1
        elif re.match(r"(-{3,}|\*{3,}|_{3,})$", s):
            flush(); out.append("<hr>"); i += 1
        elif s.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            flush()
            head = _cells(s)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i])); i += 1
            body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append('<div class="tscroll"><table class="t"><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>" + body + "</tbody></table></div>")
        elif s.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip()); i += 1
            out.append("<blockquote>" + inline(" ".join(quote)) + "</blockquote>")
        elif re.match(r"([-*+]|\d+\.)\s", s):
            flush()
            ordered = bool(re.match(r"\d+\.", s))
            items = []
            while i < len(lines) and re.match(r"\s*([-*+]|\d+\.)\s", lines[i]):
                items.append(re.sub(r"^\s*([-*+]|\d+\.)\s+", "", lines[i]))
                i += 1
                while i < len(lines) and lines[i].strip() and not re.match(r"\s*([-*+]|\d+\.)\s", lines[i]) and lines[i].startswith(" "):
                    items[-1] += " " + lines[i].strip(); i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
        else:
            para.append(s); i += 1
    flush()
    return "\n".join(out)
