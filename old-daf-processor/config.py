# Models — Haiku for mechanical passes, Sonnet for quality rewrite
SEGMENTATION_MODEL = "claude-haiku-4-5-20251001"
REWRITE_MODEL = "claude-sonnet-4-6"
SOURCE_INSERTION_MODEL = "claude-haiku-4-5-20251001"

# Max output tokens per pass.
# Pass 1 (segmentation JSON) is compact — 8K is ample.
# Pass 2 (rewrite) can be 12K–20K for a 45-min shiur; 32K gives headroom.
# Pass 3 (source insertion) outputs the full essay PLUS all Sefaria blockquotes;
# allow up to 32K (raise further if very long shiurim are still truncated).
SEGMENTATION_MAX_TOKENS = 8192
REWRITE_MAX_TOKENS = 32000
SOURCE_INSERTION_MAX_TOKENS = 32000

# Batch API settings
BATCH_POLL_INTERVAL = 30    # seconds between status polls
BATCH_TIMEOUT = 14400       # 4 hours max before giving up and saving state

# Direct API settings
DEFAULT_WORKERS = 3         # parallel workers
