// The live-text layout of one amud (daf-processor/page_layout/compact.py), for any daf: read from
// the Cloudflare R2 bucket (daf-layout/<Tractate>/<amud>.json, uploaded by page_layout/upload_r2.py)
// and served from this site, since the bucket allows no cross-site reads. The CDN keeps each
// answer a day (layouts can be redone), and a missing amud a day too.
const BASE = "https://pub-eb334b82c1044383990a6d6eba5d0956.r2.dev/daf-layout";

module.exports = async (req, res) => {
  const t = String((req.query && req.query.t) || ""), a = String((req.query && req.query.a) || "");
  if (!/^[A-Za-z' _-]{3,40}$/.test(t) || !/^\d{1,3}[ab]$/.test(a)) {
    res.status(400).json({ error: "Missing or malformed tractate or amud" });
    return;
  }
  let up;
  try {
    up = await fetch(`${BASE}/${encodeURIComponent(t)}/${a}.json`);
  } catch {
    up = null;
  }
  if (up && up.status === 404) {
    res.setHeader("Cache-Control", "public, s-maxage=86400");
    res.status(404).json({ error: "No layout for this amud" });
    return;
  }
  if (!up || !up.ok) {
    res.status(502).json({ error: "Layout unavailable" });
    return;
  }
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800");
  res.send(await up.text());
};
