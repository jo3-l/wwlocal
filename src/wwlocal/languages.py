"""Programming languages named in a posting: a small alias list and a matcher over its text."""

from __future__ import annotations

import re
from collections.abc import Iterable

# name → aliases. Aliases match case-insensitively at word boundaries, except for names in
# CASE_SENSITIVE (ordinary words in lowercase) and "re:" aliases, which are regexes that carry
# their own right-hand context: one-letter names and "Go" only count next to other languages.
LANGUAGES: dict[str, list[str]] = {
    "Python": ["Python"],
    "JavaScript": ["JavaScript", "JS", "ES6", "ECMAScript"],
    "TypeScript": ["TypeScript", "TS"],
    "Java": ["Java"],
    "C": [r"re:C(?=\s*[,/]|\s+(?i:and|or|programming|language)\b|[ \t]*$)"],
    "C++": ["C++", "CPP"],
    "C#": ["C#", "C-Sharp", "CSharp"],
    "Go": [
        "Golang",
        r"re:Go(?=\s*[,/()]|\s+(?i:and|or|programming|language|developer|engineer)\b|[ \t]*$)",
    ],
    "Rust": ["Rust"],
    "Kotlin": ["Kotlin"],
    "Swift": ["Swift", "SwiftUI"],
    "Objective-C": ["Objective-C", "ObjC"],
    "Ruby": ["Ruby", "Ruby on Rails"],
    "PHP": ["PHP"],
    "Scala": ["Scala"],
    "R": ["RStudio", r"re:R(?=\s*[,/()]|\s+(?i:and|or|programming|language|studio)\b|[ \t]*$)"],
    "MATLAB": ["MATLAB", "Simulink"],
    "Dart": ["Dart", "Flutter"],
    "Elixir": ["Elixir"],
    "Erlang": ["Erlang"],
    "Haskell": ["Haskell"],
    "OCaml": ["OCaml"],
    "Clojure": ["Clojure"],
    "F#": ["F#"],
    "Lua": ["Lua"],
    "Perl": ["Perl"],
    "Julia": ["Julia"],
    "Zig": ["Zig"],
    "Fortran": ["Fortran"],
    "COBOL": ["COBOL"],
    "Solidity": ["Solidity"],
    "SQL": ["SQL", "T-SQL", "PL/SQL"],
    "HTML": ["HTML", "HTML5"],
    "CSS": ["CSS", "CSS3", "Sass", "SCSS"],
    "Shell": ["Bash", "shell scripting", "shell scripts", "PowerShell", "zsh"],
    "Verilog": ["Verilog", "SystemVerilog", "VHDL"],
    "Assembly": ["assembly language", "x86 assembly", "ARM assembly"],
    "CUDA": ["CUDA"],
}
CASE_SENSITIVE = {"Rust", "Swift", "Dart", "Julia", "Zig", "Ruby", "Scala", "Lua", "Perl"}

# Field keys scanned, most telling first: a language's position in the result is its first
# mention in this order.
FIELDS = ["job_title", "required_skills", "job_summary", "job_responsibilities"]

_LEFT = r"(?<![A-Za-z0-9+#])"
_RIGHT = r"s?(?![A-Za-z+#])"  # a plural s is fine; a following letter means a longer word


def _group(aliases: Iterable[str]) -> str:
    """Alternation over `aliases`, dispatched on the first character and longest first within
    it, so the engine rejects most text positions after a single comparison."""
    by_first: dict[str, list[str]] = {}
    for a in sorted(aliases, key=len, reverse=True):
        by_first.setdefault(a[0], []).append(a[1:])
    alts = []
    for ch, tails in by_first.items():
        rest = "|".join(re.escape(t) for t in tails if t)
        optional = "?" if "" in tails else ""
        alts.append(re.escape(ch) + (f"(?:{rest}){optional}" if rest else ""))
    return "|".join(alts)


def _compile():
    """One regex for everything: a case-insensitive branch, a case-sensitive one, and the
    context regexes, each under a named group so the match says which table names it. One
    scan beats one per case class, and a single alternation resolves overlaps the way the old
    sort did — leftmost, then longest — because no two classes can match at the same start."""
    ci: dict[str, str] = {}
    cs: dict[str, str] = {}
    ctx: dict[str, str] = {}  # group name → language
    parts: list[str] = []
    for name, aliases in LANGUAGES.items():
        for a in aliases:
            if a.startswith("re:"):
                g = f"x{len(ctx)}"
                ctx[g] = name
                parts.append(f"(?P<{g}>{a[3:]})")
            elif name in CASE_SENSITIVE:
                cs[a] = name
            else:
                ci[a.lower()] = name
    parts[:0] = [
        "(?P<ci>(?i:" + _group(ci) + "))" + _RIGHT,
        "(?P<cs>" + _group(cs) + ")" + _RIGHT,
    ]
    return re.compile(_LEFT + "(?:" + "|".join(parts) + ")", re.M), ci, cs, ctx


_RX, _CI_NAMES, _CS_NAMES, _CTX_NAMES = _compile()


def find(text: str) -> list[tuple[str, str]]:
    """(name, matched text) for every language mention in `text`, left to right."""
    out = []
    for m in _RX.finditer(text):
        g = m.lastgroup
        assert g is not None
        if g == "ci":
            name = _CI_NAMES[m.group(g).lower()]
        elif g == "cs":
            name = _CS_NAMES[m.group(g)]
        else:
            name = _CTX_NAMES[g]
        out.append((name, m.group()))
    return out


def languages(fields: dict | None, title: str | None = None) -> list[dict]:
    """[{name, forms}] for the languages a posting names, in order of first mention across
    FIELDS. `forms` are the distinct strings that matched, which the viewer paints over."""
    texts = {k: _text((fields or {}).get(k)) for k in FIELDS}
    if title:
        texts["job_title"] = title
    forms: dict[str, list[str]] = {}
    for key in FIELDS:
        for name, form in find(texts[key]):
            seen = forms.setdefault(name, [])
            if form not in seen:
                seen.append(form)
    return [{"name": name, "forms": fs} for name, fs in forms.items()]


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return v.get("text") or " ".join(v.get("list") or [])
