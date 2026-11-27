"""Bring recorded narration into the video: python3 voice/import.py <folder with title.m4a, s1.m4a ... s6.m4a, end.m4a>
Trims the silence at each end, evens out the loudness (EBU R128, -16 LUFS), writes public/voice/<id>.wav and the lengths
to public/voice/durations.json. Then render Demo90v-16x9 / Demo90v-9x16; any scene too short for its line slows down to fit."""
import glob, json, os, re, subprocess, sys
# --edit calm90: the calm cut's recordings (public/voice/calm90); then render calm90v-16x9 / calm90v-9x16
src, here = sys.argv[1], os.path.dirname(os.path.abspath(__file__))
edit = sys.argv[sys.argv.index("--edit") + 1] if "--edit" in sys.argv else None
out = os.path.join(here, "..", "public", "voice", *([edit] if edit else [])); durs = json.load(open(os.path.join(out, "durations.json")))
trim = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse,loudnorm=I=-16:TP=-1.5:LRA=11"
for f in sorted(glob.glob(os.path.join(src, "*"))):
    k = os.path.splitext(os.path.basename(f))[0].lower()
    if k not in durs: print("skipped (not a line id):", f); continue
    w = os.path.join(out, k + ".wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", f, "-af", trim, "-ar", "48000", "-ac", "1", w], check=True)
    durs[k] = round(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", w])), 2)
    print(k, durs[k], "s")

def word_starts(w, n=5):
    """When each word of the end line starts (The Talmud / Explicated / Annotated / Illustrated / iTalmud.com):
    after each of the line's n-1 longest pauses. The end card shows each word as it is spoken."""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", w, "-af", "silencedetect=noise=-35dB:d=0.1", "-f", "null", "-"], capture_output=True, text=True).stderr
    ev = [(m.group(1), float(m.group(2))) for m in re.finditer(r"silence_(start|end): ([\d.]+)", log)]
    gaps, cur = [], None
    for kind, t in ev:
        if kind == "start":
            if gaps and t - gaps[-1][1] < 0.05: cur = gaps.pop()[0]   # two silences a hair apart are one pause
            else: cur = t
        elif cur is not None: gaps.append((cur, t)); cur = None
    gaps = [g for g in gaps if g[0] > 0.05]
    top = sorted(sorted(gaps, key=lambda g: g[1] - g[0], reverse=True)[:n - 1])
    return [0.0] + [round(g[1], 2) for g in top] if len(top) == n - 1 else None
if os.path.exists(os.path.join(out, "end.wav")):
    b = word_starts(os.path.join(out, "end.wav"))
    if b: durs["end_beats"] = b; print("end card words at", b)
    else: durs.pop("end_beats", None); print("end line: couldn't find its four pauses; the card keeps its own timing")
json.dump(durs, open(os.path.join(out, "durations.json"), "w"), indent=1)
