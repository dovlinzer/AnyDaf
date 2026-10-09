"""Automatic checklist for a generated picture. A vision model (claude-sonnet-4-5) reports pass/fail on the rules we
learned. Usage: check_picture.py image.jpg --boxes 2 --cast "a man with a spade; an ox" --numerals "10,9" --scene "one-sentence description"
Hard failures (exit code 1): boxes, text, numerals, cast, faces, badges, scene. Warnings (do not fail): white background, dead-animal convention.
Exit code 0 if no hard failure, 1 otherwise. Prints JSON. Use in the batch loop: regenerate on exit code 1."""
import argparse, base64, io, json, sys, urllib.request
from PIL import Image
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from detect_boxes import KEY
TOOL = {"name": "report", "description": "checklist result", "input_schema": {"type": "object", "properties": {
    "framed_box_count": {"type": "integer", "description": "number of framed rounded boxes floating above or beside the main scene"},
    "letters_or_words_visible": {"type": "boolean", "description": "any readable letters or words anywhere (ignore the numerals the prompt allowed)"},
    "unexpected_numerals": {"type": "boolean", "description": "numerals present that were NOT in the allowed list"},
    "extra_people_or_animals": {"type": "array", "items": {"type": "string"}, "description": "people or animals present that are not in the expected cast"},
    "missing_cast": {"type": "array", "items": {"type": "string"}, "description": "expected cast members not visible"},
    "figure_without_full_face": {"type": "boolean", "description": "any figure with a blank or featureless face"},
    "background_plain_white": {"type": "boolean", "description": "the backdrop is plain white or cut out, not a filled sky/setting"},
    "dead_animal_not_on_back_with_x_eyes": {"type": "boolean", "description": "a dead animal is shown but NOT on its back with legs up and X eyes (false if there is no dead animal)"},
    "badge_scale_or_coins_drawn": {"type": "boolean", "description": "a balance scale, coins or payment badge was drawn (they must not be)"},
    "scene_matches_description": {"type": "boolean"}, "mismatch_notes": {"type": "string"}},
    "required": ["framed_box_count", "letters_or_words_visible", "unexpected_numerals", "extra_people_or_animals", "missing_cast", "figure_without_full_face", "background_plain_white", "dead_animal_not_on_back_with_x_eyes", "badge_scale_or_coins_drawn", "scene_matches_description", "mismatch_notes"]}}
def check(path, boxes, cast, numerals, scene, allow_badge=False):
    im = Image.open(path).convert("RGB"); buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    q = (f"Inspect this generated clay-style illustration strictly. Expected framed boxes: {boxes}. Expected cast (and nothing else): {cast}. "
         f"Allowed numerals: {numerals or 'none'}. Intended scene: {scene}. Report the checklist honestly; do not be lenient.")
    body = {"model": "claude-sonnet-4-5", "max_tokens": 700, "tools": [TOOL], "tool_choice": {"type": "tool", "name": "report"},
            "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}, {"type": "text", "text": q}]}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=120)); res = [b for b in r["content"] if b["type"] == "tool_use"][0]["input"]
    fails = []
    if res["framed_box_count"] != boxes: fails.append(f"boxes: found {res['framed_box_count']}, expected {boxes}")
    if res["letters_or_words_visible"]: fails.append("letters/words visible")
    if res["unexpected_numerals"]: fails.append("unexpected numerals")
    if res["extra_people_or_animals"]: fails.append("extra: " + ", ".join(res["extra_people_or_animals"]))
    if res["missing_cast"]: fails.append("missing: " + ", ".join(res["missing_cast"]))
    if res["figure_without_full_face"]: fails.append("figure without full face")
    if res["badge_scale_or_coins_drawn"] and not allow_badge: fails.append("scale/coins/badge drawn")
    if not res["scene_matches_description"]: fails.append("scene mismatch: " + res["mismatch_notes"])
    warnings = []
    if res["background_plain_white"]: warnings.append("plain white background (cosmetic)")
    if res["dead_animal_not_on_back_with_x_eyes"]: warnings.append("dead-animal convention (check by eye)")
    res["warnings"] = warnings
    return fails, res
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("image"); ap.add_argument("--boxes", type=int, default=0); ap.add_argument("--cast", default="")
    ap.add_argument("--numerals", default=""); ap.add_argument("--scene", default=""); ap.add_argument("--allow-badge", action="store_true")
    a = ap.parse_args(); fails, res = check(a.image, a.boxes, a.cast, a.numerals, a.scene, a.allow_badge)
    print(json.dumps({"pass": not fails, "fails": fails, "warnings": res["warnings"]}, ensure_ascii=False)); sys.exit(1 if fails else 0)
