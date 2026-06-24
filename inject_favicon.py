#!/usr/bin/env python3
"""
inject_favicon.py — Sisipkan favicon emoji ke semua file HTML WebVolt

Cara pakai:
  python3 inject_favicon.py                    # dry-run, lihat preview saja
  python3 inject_favicon.py --write            # eksekusi update semua file
  python3 inject_favicon.py --write --emoji 🔥 # pakai emoji lain

Strategi:
  - Pakai SVG inline via data URI — tidak butuh file .ico/.png
  - Tidak ada request HTTP tambahan → kontribusi positif ke PSI
  - Insert tepat sebelum </head> kalau belum ada favicon
  - Kalau sudah ada favicon lama, REPLACE dengan yang baru
  - Aman dijalankan berulang (idempotent)
"""
import argparse
import os
import re
from pathlib import Path

# ── Konfigurasi ──────────────────────────────────────────────────────────────
DEFAULT_EMOJI = "⚡"      # ganti ke emoji lain kalau mau

# Folder HTML yang akan diproses (relatif dari lokasi script)
HTML_DIRS = [
    "",        # index.html
    "",        # 16 niche T2
    "",        # 18 niche T3
]

# Kalau file tier1 ada di folder sendiri, tambahkan di sini:
# HTML_DIRS.append("output-webvolt-tier1")

# ── Builder ───────────────────────────────────────────────────────────────────
def build_favicon_tag(emoji: str) -> str:
    """
    Buat tag <link> favicon SVG inline.
    Emoji di-encode manual (hanya karakter yang perlu di-encode di data URI).
    """
    # Ganti karakter yang perlu di-escape di dalam atribut HTML
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        f"<text y='.9em' font-size='90'>{emoji}</text>"
        f"</svg>"
    )
    # Encode karakter khusus untuk data URI (minimal encoding)
    svg_encoded = (
        svg
        .replace("#", "%23")
        .replace('"', "'")
        .replace("<", "%3C")
        .replace(">", "%3E")
    )
    return f'  <link rel="icon" href="data:image/svg+xml,{svg_encoded}">'


# Pola regex untuk mendeteksi favicon yang sudah ada
FAVICON_PATTERN = re.compile(
    r'\s*<link[^>]+rel=["\'](?:shortcut )?icon["\'][^>]*>\n?',
    re.IGNORECASE
)
APPLE_TOUCH_PATTERN = re.compile(
    r'\s*<link[^>]+rel=["\']apple-touch-icon["\'][^>]*>\n?',
    re.IGNORECASE
)


def process_file(filepath: Path, favicon_tag: str, write: bool) -> dict:
    """Proses satu file HTML. Return dict dengan status."""
    content = filepath.read_text(encoding="utf-8")
    original = content

    already_has_favicon = bool(FAVICON_PATTERN.search(content))

    if already_has_favicon:
        # Replace favicon yang sudah ada
        content = FAVICON_PATTERN.sub(f"\n{favicon_tag}\n", content, count=1)
        action = "REPLACED"
    else:
        # Insert sebelum </head>
        if "</head>" not in content:
            return {"file": filepath.name, "status": "SKIP", "reason": "tidak ada </head>"}
        content = content.replace("</head>", f"{favicon_tag}\n</head>", 1)
        action = "INSERTED"

    changed = content != original

    if write and changed:
        filepath.write_text(content, encoding="utf-8")

    return {
        "file":    filepath.name,
        "status":  action if changed else "NO_CHANGE",
        "changed": changed,
    }


def main():
    parser = argparse.ArgumentParser(description="Inject favicon emoji ke semua HTML WebVolt")
    parser.add_argument("--write",  action="store_true", help="Eksekusi update file (default: dry-run)")
    parser.add_argument("--emoji",  default=DEFAULT_EMOJI, help=f"Emoji favicon (default: {DEFAULT_EMOJI})")
    parser.add_argument("--dir",    action="append", help="Tambah folder HTML ekstra")
    args = parser.parse_args()

    emoji       = args.emoji
    favicon_tag = build_favicon_tag(emoji)
    dirs        = HTML_DIRS + (args.dir or [])

    mode = "✏️  WRITE MODE" if args.write else "👁️  DRY-RUN (tambah --write untuk eksekusi)"
    print("=" * 64)
    print(f"inject_favicon.py — {mode}")
    print(f"Emoji  : {emoji}")
    print(f"Tag    : {favicon_tag[:80]}...")
    print("=" * 64)

    # Kumpulkan semua file HTML
    all_files: list[Path] = []
    for d in dirs:
        folder = Path(d)
        if not folder.exists():
            print(f"  ⚠️  Folder tidak ditemukan: {d}")
            continue
        htmls = sorted(folder.glob("*.html"))
        all_files.extend(htmls)

    if not all_files:
        print("❌ Tidak ada file HTML yang ditemukan. Cek folder di HTML_DIRS.")
        return

    print(f"\nTotal file ditemukan: {len(all_files)}\n")

    results = []
    for fp in all_files:
        r = process_file(fp, favicon_tag, write=args.write)
        results.append(r)
        icon = {"INSERTED": "✅", "REPLACED": "🔄", "NO_CHANGE": "➖", "SKIP": "⚠️"}.get(r["status"], "?")
        print(f"  {icon} [{r['status']:10}] {r['file']}")

    inserted  = sum(1 for r in results if r["status"] == "INSERTED")
    replaced  = sum(1 for r in results if r["status"] == "REPLACED")
    no_change = sum(1 for r in results if r["status"] == "NO_CHANGE")
    skipped   = sum(1 for r in results if r["status"] == "SKIP")

    print("\n" + "=" * 64)
    print(f"Ringkasan:")
    print(f"  ✅ Inserted  : {inserted}")
    print(f"  🔄 Replaced  : {replaced}")
    print(f"  ➖ No change : {no_change}")
    print(f"  ⚠️  Skipped   : {skipped}")
    print(f"  Total        : {len(results)}")

    if not args.write:
        print("\n💡 Ini hanya DRY-RUN — file belum diubah.")
        print("   Jalankan ulang dengan --write untuk eksekusi:")
        print("   python3 inject_favicon.py --write")
    else:
        print(f"\n✅ Selesai! Favicon '{emoji}' sudah disuntikkan ke {inserted + replaced} file.")
    print("=" * 64)


if __name__ == "__main__":
    main()
