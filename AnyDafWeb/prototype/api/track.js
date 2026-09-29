// Shiurim stored as "soundcloud-track://<id>" (episode_audio): resolves the track to its playable
// MP3 the way the apps do (AudioPlayer.resolveStreamURL: the track's progressive transcoding, then
// its signed CDN URL) and redirects the <audio> element there. SoundCloud's API can't be called
// from the page itself (no CORS). The client id comes from the page, which reads it from
// app_config as the apps do, so no key lives in this file. Signed URLs expire: never cached.
module.exports = async (req, res) => {
  const q = req.query || {};
  const id = String(q.id || ""), cid = String(q.cid || "");
  res.setHeader("Cache-Control", "no-store");
  if (!/^\d{3,15}$/.test(id) || !/^[A-Za-z0-9]{16,64}$/.test(cid)) {
    res.status(400).json({ error: "Missing or malformed id" });
    return;
  }
  try {
    const t = await fetch(`https://api-v2.soundcloud.com/tracks/${id}?client_id=${cid}`);
    if (!t.ok) throw new Error(`track ${t.status}`);
    const j = await t.json();
    const prog = ((j.media || {}).transcodings || []).find((x) => (x.format || {}).protocol === "progressive");
    if (!prog || !j.track_authorization) throw new Error("no progressive stream");
    const s = await fetch(`${prog.url}?client_id=${cid}&track_authorization=${encodeURIComponent(j.track_authorization)}`);
    if (!s.ok) throw new Error(`stream ${s.status}`);
    const { url } = await s.json();
    if (!/^https:\/\//.test(url || "")) throw new Error("no stream url");
    res.statusCode = 302;
    res.setHeader("Location", url);
    res.end();
  } catch (e) {
    res.status(502).json({ error: "Audio unavailable", detail: String(e.message || e) });
  }
};
