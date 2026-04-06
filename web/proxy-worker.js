/**
 * AnyDaf Cloudflare Worker — SoundCloud stream URL resolver
 * ----------------------------------------------------------
 * Resolves a SoundCloud track ID to a playable CDN URL and returns it
 * with CORS headers so the web widget can fetch it from any origin.
 *
 * Deploy:
 *   1. Go to https://workers.cloudflare.com/ and create a free account.
 *   2. Create a new Worker, paste this file's contents.
 *   3. Deploy — you'll get a URL like https://anydaf-proxy.YOUR-NAME.workers.dev
 *   4. Set that URL as PROXY_URL in anydaf-widget.html.
 *
 * Usage:
 *   GET https://your-worker.workers.dev?track_id=1004549059
 *   → { "url": "https://cf-media.sndcdn.com/..." }
 */

const CLIENT_ID = "1IzwHiVxAHeYKAMqN0IIGD3ZARgJy2kl";

const CORS = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Content-Type":                 "application/json",
};

export default {
  async fetch(request) {
    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    const { searchParams } = new URL(request.url);
    const trackId = searchParams.get("track_id");
    if (!trackId) {
      return new Response(JSON.stringify({ error: "track_id required" }), { status: 400, headers: CORS });
    }

    try {
      // Step 1: get track metadata (includes track_authorization JWT + transcoding URLs)
      const trackRes = await fetch(
        `https://api-v2.soundcloud.com/tracks/${trackId}?client_id=${CLIENT_ID}`
      );
      if (!trackRes.ok) throw new Error(`Track fetch: ${trackRes.status}`);
      const track = await trackRes.json();

      const auth = track.track_authorization;
      const transcodings = track?.media?.transcodings ?? [];

      // Prefer progressive (direct MP3) over HLS
      const progressive = transcodings.find(
        t => t?.format?.protocol === "progressive"
      );
      if (!progressive) throw new Error("No progressive transcoding found");

      // Step 2: resolve transcoding URL → signed CDN URL
      const tcURL = `${progressive.url}?client_id=${CLIENT_ID}&track_authorization=${auth}`;
      const streamRes = await fetch(tcURL);
      if (!streamRes.ok) throw new Error(`Stream resolve: ${streamRes.status}`);
      const { url } = await streamRes.json();
      if (!url) throw new Error("No URL in stream response");

      return new Response(JSON.stringify({ url }), { headers: CORS });

    } catch (err) {
      return new Response(
        JSON.stringify({ error: err.message }),
        { status: 502, headers: CORS }
      );
    }
  },
};
