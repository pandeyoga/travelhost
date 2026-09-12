#!/usr/bin/env python3
"""_codemod_string_bounds.py — SEKALI PAKAI: memasang `max_length` pada field teks sensitif.

Latar belakang (bug nyata, bukan dugaan): guardrail adversarial `verify_adversarial_5xx.py`
mengirim `"A" * 60000` ke endpoint tulis. Semua endpoint benar TIDAK 5xx — itu yang diuji —
tetapi nilainya TERSIMPAN karena tidak satu pun field teks punya batas panjang. Akibatnya
`customers.name` berisi 60.000 karakter, dan booking yang memakainya MERUSAK tata letak tabel
ERP (baris melebar tak wajar) serta akan merusak PDF invoice/slip dan payload WhatsApp.

Skrip ini dijalankan SEKALI untuk memasang batas pada field bernama sensitif (identitas, label,
teks pendek) di seluruh `backend/schemas*.py`. Setelah itu penjaga statik INV-STR-01
(`scripts/guardrails/verify_string_bounds.py`) yang menjaga agar field BARU tidak lupa dibatasi.

Jalankan:  python scripts/_codemod_string_bounds.py --apply     (tanpa --apply = pratinjau)
"""
import argparse
import ast
import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent / "backend"

# Batas per NAMA field. Angka dipilih dari kenyataan pemakaian, bukan angka bulat sembarangan:
# nomor telepon Indonesia terpanjang + kode negara < 24; pesan WhatsApp maksimal 4096 karakter;
# alamat penjemputan hotel/patokan jarang > 300.
LIMITS = {
    "name": 120, "phone": 24, "email": 160, "code": 32, "plate_number": 24,
    "label": 120, "title": 200, "city": 80, "address": 300, "reason": 400,
    "sender_name": 120, "bank": 60, "origin": 160, "destination": 160,
    "note": 1000, "notes": 2000, "message": 4000, "password": 200,
    "role": 32, "status": 32, "type": 40, "slug": 120, "subject": 200,
}


def split_comment(text: str):
    """Pisahkan komentar akhir baris agar tidak ikut diubah/dipindah."""
    in_str, quote = False, ""
    for i, ch in enumerate(text):
        if in_str:
            if ch == quote:
                in_str = False
            continue
        if ch in "\"'":
            in_str, quote = True, ch
        elif ch == "#":
            return text[:i].rstrip(), text[i:]
    return text, ""


def insert_into_field(code: str, limit: int) -> str:
    """Sisipkan `max_length=` di dalam pemanggilan Field(...) yang sudah ada."""
    idx = code.index("Field(")
    depth, i = 0, idx + len("Field(") - 1
    while i < len(code):
        if code[i] == "(":
            depth += 1
        elif code[i] == ")":
            depth -= 1
            if depth == 0:
                inner = code[idx + len("Field("):i].strip()
                sep = ", " if inner else ""
                return f"{code[:i]}{sep}max_length={limit}{code[i:]}"
        i += 1
    raise ValueError(f"Field( tidak tertutup: {code!r}")


def rewrite_decl(code: str, limit: int) -> str:
    body, comment = split_comment(code)
    pad = "  " if comment else ""   # PEP8: minimal dua spasi sebelum komentar sebaris
    if "Field(" in body:
        out = insert_into_field(body, limit)
    elif "=" in body:
        target, default = body.split("=", 1)
        out = f"{target.rstrip()} = Field(default={default.strip()}, max_length={limit})"
    else:
        out = f"{body} = Field(max_length={limit})"
    return f"{out}{pad}{comment}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    total = 0
    for path in sorted(BACKEND.glob("schemas*.py")):
        src = path.read_text()
        lines = src.splitlines(keepends=True)
        edits = []  # (start_line, end_line, new_text)
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.ClassDef):
                continue
            for st in node.body:
                if not (isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)):
                    continue
                ann = ast.unparse(st.annotation)
                if not re.search(r"\bstr\b", ann) or "ict" in ann:
                    continue
                limit = LIMITS.get(st.target.id)
                if limit is None:
                    continue
                seg = "".join(lines[st.lineno - 1:st.end_lineno])
                if "max_length" in seg:
                    continue
                indent = re.match(r"\s*", seg).group(0)
                nl = "\n" if seg.endswith("\n") else ""
                new = indent + rewrite_decl(seg.strip(), limit) + nl
                edits.append((st.lineno - 1, st.end_lineno, new,
                              f"{path.name}:{node.name}.{st.target.id}"))
        for start, end, new, tag in sorted(edits, reverse=True):
            print(f"  {tag}\n    - {''.join(lines[start:end]).strip()}\n    + {new.strip()}")
            lines[start:end] = [new]
        total += len(edits)
        if args.apply and edits:
            path.write_text("".join(lines))
    print(f"\n{'DITERAPKAN' if args.apply else 'PRATINJAU'}: {total} field teks dibatasi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
