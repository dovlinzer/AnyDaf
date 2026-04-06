#!/usr/bin/env python3
"""
build-pages.py
--------------
Enumerates Talmud page images from public Google Drive folders and writes
pages.json, which maps { tractate → { page_number → drive_file_id } }.

The iOS app uses the file IDs to construct Google Drive thumbnail URLs:
    https://drive.google.com/thumbnail?id=FILE_ID&sz=w1200

Page number ↔ daf conversion (used by the app, shown here for reference):
    daf  = XX // 2 + 1   (where XX is the page number)
    side = "a" if XX % 2 == 0 else "b"
    Inverse: XX = (daf - 1) * 2  [side a]
             XX = (daf - 1) * 2 + 1  [side b]

Requirements:
    - Google Drive API v3 enabled in Google Cloud Console
    - An API key (no OAuth needed — works for any publicly shared folder)

Usage:
    cd /Users/dovlinzer/claudecode/AnyDaf/web
    python3 build-pages.py --api-key AIzaSyAocLdmjrsJBIEXmnh0iri1S6L9OfNDqMc


    # Add or update a specific tractate folder:
    python3 build-pages.py --api-key KEY --tractate Berakhot --folder-id FOLDER_ID
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — add folder IDs here as you upload more tractates
# ---------------------------------------------------------------------------

TRACTATE_FOLDERS = {
    "Berakhot": "1b1r0oLmulopGjvwintjCVeYfL4x0EuAq",
    "Shabbat": "1TBaz0P681WLPtswLbZjZtehqNci0TnLh",
    "Eiruvin": "1J1N_96JIRZCjYTdLoQvhfbMtu-WjHtUk",
    "Pesachim": "1cpYyi7HryiLW8x1rJrTKQ6FGC443zL4f",
    "Shekalim": "1T308n70TK6F9o3hP6K7lztJVFByNUj4Z",
    "Rosh Hashanah":"1l2INAjwr3-iMJkLcDPyXU1DUp05wp35C",
    "Yoma": "1VVpYP3aGbwViiCO47KsdraUhUwTBxgPZ",
    "Sukkah": "1lq8Il-kFyo4ODLkvznXHtulO5_msXwCj",
    "Beitzah": "1lcIrVlhg_5IVvNkIn05XbMauFtbnkvvK",
    "Ta'anit": "1ODuEIVPC9ZUn0ahnGLIlaCih3TixM4-j",
    "Megillah": "1Ce-HISiB0oRjmdAGvFxtfh51MVSTPcFM",
    "Moed Katan": "1jlizJWNYKdlQj0aL5BjuyEGTeYZDGGvM",
    "Chagigah": "12g0Oa-S13tQUTHIzZXQ7--smUFrwQG9_",
    "Yevamot": "1baXz5gjDGfNu2abAgJ-_d3j4Ackc46SL",
    "Ketubot": "1gtWhLWYZ1Z93cE_17Qiy8MysI3X_9PkW",
    "Nedarim": "1OTkCo-vc3wsxv0aokYaG22eklmZZaipo",
    "Nazir": "11m_EwwKJxaiJHwFF1HhcVhMwUXsPqUL8",
    "Sotah": "1GRGizfxyI5A34Csr1u1W38ge81TUiwXe",
    "Gittin": "16LZ1THsL2UaS6usjnOanGAM960on36fr",
    "Kiddushin": "1p80YsNtnpH9hKP-MeAGjsh7-jiiO74PS",
    "Bava Kamma": "1PIVL6saQoIdIuK96edcgIpmQLSUBVNdv",
    "Bava Metzia": "1FqYtOAVzqrlnQmmFXp_XkhYuL3gEvroW",
    "Bava Batra": "1w4eMNOsmlOnEbVZ_8lUucDC71XZ-1SbU",
    "Sanhedrin": "1uj70NcbLkLaQyRbMeYbANV14QakwkJsA",
    "Makkot": "1_4npiORdNPqZJ2rTAj6IRjntEzJ_mL7F",
    "Shevuot": "13OYRwlk6btDI_ed9oHOetRb-ktR6zeep",
    "Avodah Zarah": "1KzqLI20F5Vu-u1375V9THAiiFnvaV-ER",
    "Horayot": "1SWfzMAoSxW_N-TIF7q0kgDalII8FpHdn",
    "Zevachim": "1bctDa_2gZVvnF1hGnGmDPrun9cS23hKb",
    "Menachot": "1apR0igBQTkXLzh7lJo0DEVms7nZR-lXk",
    "Hullin": "15mG6vHhzj1mqljpD1qwVJsAZig1BDd-Y",
    "Bekhorot": "1aPSF63l6kJZgse4Zg7BjgYuUoMiNjatF",
    "Arakhin": "1mwGaoUs-Qa69Bvr__LrtIWy6PNExuxnl",
    "Temurah": "1JCGd5dKYE4Rtd7b7HgudCi3ofHZGHKQP",
    "Keritot": "15y1iZdcveEqwmehxy7ukRc0XfV9mxFrT",
    "Meilah": "1jvmLRIog03nVu1EMnnKdLgwMyTqRl2SC",
    "Kinnim": "1VPPIN9GMyWBUAXkMoAryfPxX01ULXT8b",
    "Tamid": "1hNeJpdQ48r9bXcP3flkcWYZAKpmTbCgf",
    "Middos": "1DWGEjuQ3qyzXff8j54SQZdnrSB1sxiNp",
    "Niddah": "1mN6pwfetLgeaYJDv9JqAmGuvBt-j-F9C"
    
    
    # "Shabbat":  "FOLDER_ID_HERE",
}

OUTPUT = Path(__file__).parent / "pages.json"

# ---------------------------------------------------------------------------
# Google Drive helpers
# ---------------------------------------------------------------------------

def fetch(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "AnyDaf-Builder/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"\nHTTP {e.code} {e.reason}")
            try:
                err = json.loads(body)
                msg = err.get("error", {}).get("message", body)
                print(f"Google API error: {msg}")
            except Exception:
                print(f"Response: {body[:500]}")
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def list_drive_folder(folder_id, api_key):
    """Returns list of (filename, file_id) for all non-trashed files in the folder."""
    files = []
    page_token = None

    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed=false",
            "fields": "nextPageToken,files(id,name)",
            "pageSize": 1000,
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        url = "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode(params)
        data = json.loads(fetch(url))
        files.extend((f["name"], f["id"]) for f in data.get("files", []))

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return files


def parse_page_number(filename, tractate):
    """
    Extract the page number XX from 'Berakhot_Page_XX.jpg' → int, or None.
    Handles .jpg, .jpeg, .png extensions case-insensitively.
    Also tries a stripped variant with all non-alphanumeric characters removed,
    e.g. "Ta\u2019anit" → "Taanit", "Rosh HaShanah" → "RoshHaShanah".
    """
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    # Build candidate prefixes: original, then alphanumeric-only (strips any
    # apostrophe variant, spaces, etc.), e.g. "Ta'anit" → "Taanit"
    clean = re.sub(r"[^a-zA-Z0-9]", "", tractate)
    candidates = dict.fromkeys([tractate, clean])
    for candidate in candidates:
        prefix = f"{candidate}_Page_"
        if stem.startswith(prefix) or stem.lower().startswith(prefix.lower()):
            try:
                return int(stem[len(prefix):])
            except ValueError:
                return None
    return None

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if "--api-key" in args:
        idx = args.index("--api-key")
        api_key = args[idx + 1]

    if not api_key:
        print("Error: provide API key via --api-key KEY or GOOGLE_API_KEY env var")
        print()
        print("To get an API key:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a project (or select existing)")
        print("  3. Enable 'Google Drive API'")
        print("  4. Go to Credentials → Create Credentials → API key")
        print("  5. (Optional) Restrict the key to Google Drive API")
        sys.exit(1)

    # Allow overriding a single tractate from the command line
    override_tractate = None
    override_folder = None
    if "--tractate" in args and "--folder-id" in args:
        override_tractate = args[args.index("--tractate") + 1]
        override_folder = args[args.index("--folder-id") + 1]

    folders_to_process = (
        {override_tractate: override_folder}
        if override_tractate
        else TRACTATE_FOLDERS
    )

    # Load existing JSON so we can merge without losing other tractates
    existing = {}
    if OUTPUT.exists():
        with open(OUTPUT, encoding="utf-8") as f:
            existing = json.load(f)

    for tractate, folder_id in folders_to_process.items():
        print(f"\n{tractate}  (folder: {folder_id})")
        files = list_drive_folder(folder_id, api_key)
        print(f"  {len(files)} files found in folder")

        page_map = {}
        skipped = []
        for name, file_id in files:
            page_num = parse_page_number(name, tractate)
            if page_num is not None:
                page_map[str(page_num)] = file_id
            else:
                skipped.append(name)

        if skipped:
            print(f"  Skipped {len(skipped)} unrecognised files: {skipped[:5]}")

        existing[tractate] = page_map
        print(f"  Indexed {len(page_map)} pages for {tractate}")

        # Show daf coverage
        page_numbers = sorted(int(k) for k in page_map)
        if page_numbers:
            lo, hi = page_numbers[0], page_numbers[-1]
            daf_lo  = lo // 2 + 1
            daf_hi  = hi // 2 + 1
            side_lo = "a" if lo % 2 == 0 else "b"
            side_hi = "a" if hi % 2 == 0 else "b"
            print(f"  Coverage: pages {lo}–{hi}  →  daf {daf_lo}{side_lo} – {daf_hi}{side_hi}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\nSaved → {OUTPUT}")


if __name__ == "__main__":
    main()
