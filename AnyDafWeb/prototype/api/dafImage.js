// Page scans for dafim without a built outline: fetches Google Drive's thumbnail server-side, as
// AnyTorahWeb's app/api/dafImage does. Pointing <img> straight at Drive fails often in browsers
// (the reader's own Google session interferes with the anonymous "anyone with the link" request).
// Only Drive thumbnails, only ids shaped like Drive file ids; the CDN keeps each page for a year.
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";

module.exports = async (req, res) => {
  const id = String((req.query && req.query.id) || "");
  if (!/^[\w-]{20,80}$/.test(id)) {
    res.status(400).json({ error: "Missing or malformed id" });
    return;
  }
  let up;
  try {
    up = await fetch(`https://drive.google.com/thumbnail?id=${id}&sz=w1600`, { headers: { "User-Agent": UA } });
  } catch {
    up = null;
  }
  const type = (up && up.headers.get("content-type")) || "";
  if (!up || !up.ok || !type.startsWith("image/")) {
    res.status(502).json({ error: "Image unavailable" });
    return;
  }
  res.setHeader("Content-Type", type);
  // A Drive file id always names the same scanned page.
  res.setHeader("Cache-Control", "public, max-age=604800, s-maxage=31536000, immutable");
  res.send(Buffer.from(await up.arrayBuffer()));
};
