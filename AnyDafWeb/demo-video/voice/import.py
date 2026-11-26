"""Bring recorded narration into the video: python3 voice/import.py <folder with title.m4a, s1.m4a ... s6.m4a, end.m4a>
Trims the silence at each end, evens out the loudness (EBU R128, -16 LUFS), writes public/voice/<id>.wav and the lengths
to public/voice/durations.json. Then render Demo90v-16x9 / Demo90v-9x16; any scene too short for its line slows down to fit."""
import glob, json, os, subprocess, sys
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
json.dump(durs, open(os.path.join(out, "durations.json"), "w"), indent=1)
