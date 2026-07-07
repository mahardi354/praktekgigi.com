#!/usr/bin/env python3
"""
Cek Lokal — Validasi Canonical & Sitemap SEBELUM upload ke hosting
====================================================================

Beda dengan cek_indexing.py (yang cek ke situs LIVE lewat internet),
script ini baca file HTML & sitemap.xml langsung dari folder hasil
generate di komputer Anda. Jadi bisa dipakai untuk validasi ratusan/
ribuan halaman dalam hitungan detik, sebelum upload/push ke hosting.

CARA PAKAI:
   Taruh script ini di folder ROOT yang berisi semua folder hasil
   generate (misal output-webvolt-index, output-webvolt-manual,
   output-webvolt-tier2, output-webvolt-tier3, output-webvolt, dst),
   lalu jalankan tanpa argumen apa pun:

       python cek_lokal.py

   Script otomatis menyisir SEMUA sub-folder untuk file .html dan
   sitemap.xml, lalu kasih ringkasan per folder + total keseluruhan.

   Kalau mau cek satu folder spesifik saja:
       python cek_lokal.py --folder ./output-webvolt-tier2

Yang dicek:
  1. Setiap file .html: apakah punya tag <link rel="canonical">?
     Apakah canonical-nya masih berakhiran .html (harusnya tidak)?
     Apakah canonical-nya "nyambung" dengan nama file itu sendiri
     (self-referencing) — untuk nangkep salah copy-paste antar halaman.
  2. Setiap sitemap.xml yang ditemukan: apakah ada entri <loc> yang
     masih berakhiran .html? Apakah jumlah URL di sitemap kira-kira
     cocok dengan jumlah file .html di folder yang sama?

Output: ringkasan di terminal (per folder + total) + file
rincian_masalah.csv di folder tempat script dijalankan, kalau ada
yang perlu dicek manual.
"""

import argparse
import csv
import re
import sys
from pathlib import Path
from collections import defaultdict

CANONICAL_RE = re.compile(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', re.IGNORECASE)
LOC_RE = re.compile(r'<loc>([^<]+)</loc>')


def check_html_file(fp: Path):
    """Cek satu file .html, kembalikan None kalau aman, atau dict masalah."""
    text = fp.read_text(encoding="utf-8", errors="ignore")
    m = CANONICAL_RE.search(text)

    if not m:
        return {"masalah": "Tidak ada tag <link rel=\"canonical\"> ditemukan", "canonical": ""}

    canonical = m.group(1)
    problems = []

    if canonical.endswith(".html"):
        problems.append("canonical masih berakhiran .html")

    expected_slug = fp.stem
    if expected_slug.lower() != "index":
        canonical_slug = canonical.rstrip("/").rsplit("/", 1)[-1]
        canonical_slug_clean = canonical_slug[:-5] if canonical_slug.endswith(".html") else canonical_slug

        if canonical_slug_clean != expected_slug:
            problems.append(
                f"canonical sepertinya menunjuk ke halaman LAIN "
                f"(file: {expected_slug}, canonical: {canonical_slug_clean})"
            )

    if problems:
        return {"masalah": " | ".join(problems), "canonical": canonical}
    return None


def check_sitemap_file(sitemap_path: Path, html_count_in_folder: int):
    text = sitemap_path.read_text(encoding="utf-8", errors="ignore")
    locs = LOC_RE.findall(text)
    html_locs = [u for u in locs if u.endswith(".html")]
    warn = None
    selisih = abs(len(locs) - html_count_in_folder)
    if selisih > 1:
        warn = (f"Jumlah URL sitemap ({len(locs)}) beda cukup jauh dari jumlah "
                f"file .html di folder yang sama ({html_count_in_folder})")
    return locs, html_locs, warn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default=".", help="Folder root untuk disisir (default: folder saat ini)")
    args = parser.parse_args()

    root = Path(args.folder)
    if not root.is_dir():
        print(f"❌ Folder tidak ditemukan: {root}")
        sys.exit(1)

    print(f"Menyisir semua sub-folder di bawah: {root.resolve()}\n")

    # kelompokkan file .html berdasarkan folder induknya masing-masing
    html_by_folder = defaultdict(list)
    for fp in sorted(root.rglob("*.html")):
        html_by_folder[fp.parent].append(fp)

    sitemap_files = sorted(root.rglob("sitemap.xml"))

    all_issues = []       # untuk CSV: (folder, file, masalah, canonical)
    total_files = 0
    total_ok = 0
    total_bad = 0

    print("=" * 70)
    print("HASIL CEK CANONICAL — per folder")
    print("=" * 70)

    for folder, files in html_by_folder.items():
        folder_ok = 0
        folder_bad = 0
        for fp in files:
            result = check_html_file(fp)
            total_files += 1
            if result is None:
                folder_ok += 1
                total_ok += 1
            else:
                folder_bad += 1
                total_bad += 1
                all_issues.append({
                    "folder": str(folder),
                    "file": fp.name,
                    "masalah": result["masalah"],
                    "canonical": result["canonical"],
                })
        status = "✅" if folder_bad == 0 else "⚠️ "
        print(f"{status} {folder}  → {len(files)} file, aman: {folder_ok}, bermasalah: {folder_bad}")

    print()
    print("=" * 70)
    print("HASIL CEK SITEMAP.XML — semua yang ditemukan")
    print("=" * 70)

    sitemap_rows = []  # untuk CSV
    if not sitemap_files:
        print("⚠️  Tidak ada sitemap.xml ditemukan di bawah folder ini.")
    else:
        for sm in sitemap_files:
            html_count_here = len(html_by_folder.get(sm.parent, []))
            locs, html_locs, warn = check_sitemap_file(sm, html_count_here)
            status = "✅" if not html_locs and not warn else "⚠️ "
            print(f"{status} {sm}")
            print(f"     Total URL: {len(locs)}  |  masih .html: {len(html_locs)}")
            if warn:
                print(f"     ⚠️  {warn}")
            for u in html_locs:
                sitemap_rows.append({
                    "folder": str(sm.parent), "file": "(sitemap.xml)",
                    "masalah": "URL masih .html", "canonical": u,
                })

    # simpan rincian ke CSV kalau ada masalah
    combined_issues = all_issues + sitemap_rows
    if combined_issues:
        out_csv = root / "rincian_masalah.csv"
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["folder", "file", "masalah", "canonical"])
            writer.writeheader()
            writer.writerows(combined_issues)
        print(f"\n📄 Rincian lengkap ({len(combined_issues)} baris) disimpan di: {out_csv}")

    print()
    print("=" * 70)
    print("RINGKASAN TOTAL")
    print("=" * 70)
    print(f"Total file .html dicek     : {total_files}")
    print(f"Aman                       : {total_ok}")
    print(f"Bermasalah                 : {total_bad}")
    print(f"Total sitemap.xml ditemukan: {len(sitemap_files)}")

    print()
    if not combined_issues:
        print("✅ SEMUA AMAN — canonical dan sitemap sudah bersih dari .html.")
        print("   Boleh lanjut upload/push ke hosting.")
    else:
        print("⚠️  Ada yang perlu diperbaiki dulu sebelum upload. Cek rincian_masalah.csv")


if __name__ == "__main__":
    main()
