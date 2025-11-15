#!/usr/bin/env python3
# clean_and_flatten_output.py
# Place this in the same folder as output.json

import json
import csv
import re
from pathlib import Path

INPUT_JSON = Path("output.json")
OUT_JSON = Path("cleaned_output.json")
OUT_CSV = Path("cleaned_output.csv")

URL_RE = re.compile(r"https?://[^\s\"',;]+", re.IGNORECASE)

def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"{path} not found in current folder.")
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    # If the file is a single object, wrap it
    if isinstance(data, dict):
        return [data]
    return list(data)

def normalize_price(p):
    if not p:
        return None, None
    s = str(p).strip()
    s = s.replace("\u00A0", " ")
    m = re.search(r'(\d{1,3}(?:[ \.,]\d{3})*(?:[,\.\s]\d{1,2})?)', s)
    if not m:
        return s, None
    raw = m.group(1)
    cleaned = raw.replace(" ", "").replace("\u202F", "")
    # decide decimal separator
    if cleaned.count(",") > 0 and cleaned.count(".") == 0:
        numeric = cleaned.replace(",", ".")
    elif cleaned.count(".") > 0 and cleaned.count(",") == 0:
        numeric = cleaned
    else:
        numeric = cleaned.replace(",", ".")
    try:
        float_val = float(numeric)
        return raw, f"{float_val:.2f}"
    except Exception:
        return raw, None

def extract_urls_from_string(s):
    if not s:
        return []
    # Try to find all http(s) URLs
    found = URL_RE.findall(s)
    if found:
        return found
    # fallback: split on commas/semicolons and look for tokens with http
    parts = re.split(r'[;,]\s*', s)
    out = []
    for p in parts:
        p = p.strip().strip('"').strip("'")
        m = URL_RE.search(p)
        if m:
            out.append(m.group(0))
        else:
            # if whole token looks like a url without scheme (rare), skip
            pass
    return out

def flatten_images_field(value):
    # Accept list, tuple, string, or other
    if not value:
        return []
    out = []
    seen = set()
    # If it's a list-like, iterate
    if isinstance(value, (list, tuple)):
        for v in value:
            if not v:
                continue
            if isinstance(v, (list, tuple, dict)):
                # try to stringify and extract urls
                urls = extract_urls_from_string(json.dumps(v, ensure_ascii=False))
            else:
                urls = extract_urls_from_string(str(v))
            for u in urls:
                uu = u.strip()
                if uu and uu not in seen:
                    seen.add(uu)
                    out.append(uu)
        return out
    # If it's a dict, try to find url-like values inside
    if isinstance(value, dict):
        for k, v in value.items():
            urls = flatten_images_field(v)
            for u in urls:
                if u not in seen:
                    seen.add(u)
                    out.append(u)
        return out
    # If it's a string: extract urls
    if isinstance(value, str):
        urls = extract_urls_from_string(value)
        for u in urls:
            uu = u.strip()
            if uu and uu not in seen:
                seen.add(uu)
                out.append(uu)
        # If none found, maybe the string is comma-separated urls without http - try splitting
        if not out:
            parts = re.split(r'[;,]\s*', value)
            for p in parts:
                p = p.strip().strip('"').strip("'")
                if p.startswith("http"):
                    if p not in seen:
                        seen.add(p)
                        out.append(p)
        return out
    # fallback: stringify
    return flatten_images_field(str(value))

def guess_image_keys(item):
    # return candidate keys that likely contain images
    keys = []
    for k in item.keys():
        kl = k.lower()
        if "image" in kl or "img" in kl or "picture" in kl or "foto" in kl or "bild" in kl:
            keys.append(k)
    # common explicit names
    for k in ("images", "image", "image_urls", "image_url", "imageUrls", "bilder", "pictures"):
        if k in item and k not in keys:
            keys.append(k)
    return keys

def clean_text(s):
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    s = s.replace("\u00A0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def main():
    try:
        items = load_json(INPUT_JSON)
    except FileNotFoundError as e:
        print("ERROR:", e)
        return

    cleaned = []
    seen_ids = set()
    removed = 0
    items_with_images = 0

    for it in items:
        if not isinstance(it, dict):
            continue
        out = {}

        uid = it.get("unique_id") or it.get("product_id") or it.get("product_url")
        if uid:
            if uid in seen_ids:
                removed += 1
                continue
            seen_ids.add(uid)

        out["product_url"] = clean_text(it.get("product_url"))
        out["product_name"] = clean_text(it.get("product_name"))

        raw_price, numeric = normalize_price(it.get("price") or it.get("regular_price") or "")
        out["price"] = raw_price or ""
        out["regular_price"] = numeric or ""
        out["currency"] = clean_text(it.get("currency") or "")

        # IMAGE HANDLING: look for likely keys and extract urls robustly
        image_urls = []
        # preferred keys if present exactly
        for preferred in ("images", "image", "image_urls", "image_url", "imageUrls"):
            if preferred in it:
                image_urls = flatten_images_field(it[preferred])
                if image_urls:
                    break
        # otherwise try guessed keys
        if not image_urls:
            for k in guess_image_keys(it):
                image_urls = flatten_images_field(it[k])
                if image_urls:
                    break
        # also check nested fields or 'media' like
        if not image_urls:
            for k, v in it.items():
                if isinstance(v, (list, dict, str)):
                    # quick heuristic: if value contains 'cdn' or 'images.cdn' try to extract
                    sval = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                    if "cdn" in sval.lower() or "http" in sval.lower():
                        urls = flatten_images_field(v)
                        if urls:
                            image_urls = urls
                            break

        out["images"] = ";".join(image_urls) if image_urls else ""
        if image_urls:
            items_with_images += 1

        out["product_description"] = clean_text(it.get("product_description") or "")
        out["unique_id"] = clean_text(it.get("unique_id") or "")
        out["product_id"] = clean_text(it.get("product_id") or "")
        out["ingredients"] = clean_text(it.get("ingredients") or "")
        out["details"] = clean_text(it.get("details") or "")

        cleaned.append(out)

    # write json
    OUT_JSON.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")

    # write csv - use fieldnames in desired order
    fieldnames = ["unique_id", "product_id", "product_name", "product_url",
                  "price", "regular_price", "currency", "product_description",
                  "ingredients", "details", "images"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in cleaned:
            row = {k: r.get(k, "") for k in fieldnames}
            writer.writerow(row)

    print(f"Converted {len(items)} items -> {len(cleaned)} cleaned items (duplicates removed: {removed}).")
    print(f"Items with images: {items_with_images} / {len(cleaned)}")
    print(f"Wrote: {OUT_JSON} and {OUT_CSV}")

if __name__ == "__main__":
    main()
