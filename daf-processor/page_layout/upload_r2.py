"""Upload the site's version of every finished amud (compact.py) to Cloudflare R2, so any daf can
show its live text, with or without an outline.

    python3 -m page_layout.upload_r2                     # dry run: what would be uploaded
    python3 -m page_layout.upload_r2 --apply
    python3 -m page_layout.upload_r2 --apply --only Berakhot Shabbat

Objects: daf-layout/<Tractate>/<amud>.json in the bucket AnyYCTorah's read-aloud audio uses
(keys from AnyYCTorah/scripts/content_index/.env: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
R2_SECRET_ACCESS_KEY, R2_BUCKET). <Tractate> is the apps' name as the web page writes it
(slugT in app.html): spaces as underscores, ’ as '  ->  daf-layout/Bava_Metzia/11a.json.
An object whose contents are unchanged is skipped (its ETag is the MD5), so reruns are cheap and
safe; rerun after page_layout reruns an amud. Short cache (a day), since layouts can be redone.
The web page reads them through its own api/layout function (same origin; the bucket allows no
cross-site reads); the phone apps can read them straight from the bucket's public address.

Needs boto3 (the system python3 has it; daf-processor's venv doesn't). No numpy needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor

from .compact import OUT, site_layout

ENV = os.path.join(os.path.dirname(__file__), "..", "..", "..", "AnyYCTorah", "scripts", "content_index", ".env")
PREFIX = "daf-layout/"
APP_NAME = {"Rosh HaShanah": "Rosh Hashanah"}    # out/ (the scans' spelling) -> the apps'


def slug(tractate_dir: str) -> str:
    return APP_NAME.get(tractate_dir, tractate_dir).replace("’", "'").replace(" ", "_")


def client():
    import boto3
    for line in open(ENV, encoding="utf-8"):
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    return boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")


def in_bucket(s3, bucket: str, prefix: str) -> dict:
    etags, token = {}, None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix, **({"ContinuationToken": token} if token else {})}
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            etags[o["Key"]] = o["ETag"].strip('"')
        if not r.get("IsTruncated"):
            return etags
        token = r["NextContinuationToken"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    s3 = client()
    bucket = os.environ["R2_BUCKET"]
    have = in_bucket(s3, bucket, PREFIX)
    todo, total, size = [], 0, 0
    for tdir in sorted(p.name for p in OUT.iterdir() if p.is_dir()):
        if a.only and tdir not in [x.replace("_", " ") for x in a.only]:
            continue
        for f in sorted(OUT.joinpath(tdir).glob("*.json")):
            amud = f.stem
            body = json.dumps(site_layout(tdir, amud), ensure_ascii=False, separators=(",", ":")).encode()
            key = f"{PREFIX}{slug(tdir)}/{amud}.json"
            total += 1
            if have.get(key) != hashlib.md5(body).hexdigest():
                todo.append((key, body)); size += len(body)
    print(f"{total} amudim; {len(todo)} to upload ({size / 1e6:.1f} MB), {total - len(todo)} unchanged")
    if not a.apply:
        print("dry run: add --apply to upload")
        return

    def put(kb):
        k, b = kb
        s3.put_object(Bucket=bucket, Key=k, Body=b, ContentType="application/json; charset=utf-8",
                      CacheControl="public, max-age=86400")
    with ThreadPoolExecutor(8) as ex:
        for i, _ in enumerate(ex.map(put, todo), 1):
            if i % 200 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
