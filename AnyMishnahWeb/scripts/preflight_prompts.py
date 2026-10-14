"""STANDING STEP before any picture prompt goes to the author (2026-10-13):
    python3 scripts/preflight_prompts.py data/<prompt file>.md
runs (1) check_prompts.py (mechanical: second moments, misfiring expression words, edit wording, poses, risk words) and (2) audit_prompts.py (content: extraneous
elements and whether the key facts of the case are VISIBLE, judged against the mishnah and the outline), then prints one summary. Read data/prompt_audit.md, fix the
MAJOR items and any key fact marked NO or WEAK, rerun, and only then send the file. prompt_diff.py against the last accepted file shows what changed."""
import subprocess, sys
f = sys.argv[1]
a = subprocess.run([sys.executable, "scripts/check_prompts.py", f], capture_output=True, text=True); print(a.stdout[-1500:])
b = subprocess.run([sys.executable, "scripts/audit_prompts.py", f] + sys.argv[2:], capture_output=True, text=True); print(b.stdout.strip() or b.stderr[-800:])
print("\nNext: read data/prompt_audit.md; fix MAJOR extras and NO/WEAK key facts; rerun. Do not send a file with unresolved MAJOR items.")
sys.exit(1 if (a.returncode or b.returncode) else 0)
