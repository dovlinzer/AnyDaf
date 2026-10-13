# Hosting note: AnyMishnah Web and AnyDaf Web (for the SiteGround GoGeek question)

## AnyMishnah Web (imishna.com): safe to host
- Static site: 7 HTML pages (40-140 KB each), 1 icon file, about 130 images; 32 MB in total.
- No database, no PHP, no server-side code, no API calls. The quiz and toggles run in the visitor's browser. The only outside request is Google Fonts.
- To move it: upload the folder. It needs two Apache rules: serve /bava-kamma-3 as bava-kamma-3.html (clean URLs), and send the header "X-Robots-Tag: noindex, nofollow" while it is private. Password protection, if wanted, would use SiteGround's own password-protect feature or basic auth in .htaccess.
- Growth: about 40 more pictures are planned (a few MB each chapter). It stays well under a few hundred MB.

## AnyDaf Web (outline site, Vercel project "anydaf-outlines"): needs more care
- Static part: 109 MB. One page of 243 KB, 73 outline data files (20 MB, about 270 KB each), 167 images (80 MB), and 2,269 small "sync" files (9 MB).
- It also has 3 small server-side functions (Node), which would have to be rewritten as PHP scripts on SiteGround:
  - /api/dafImage: fetches a page image from Google Drive and passes it on, cached for a year by Vercel's CDN. On SiteGround it needs its own caching or a CDN in front, or each view re-downloads from Drive.
  - /api/layout: fetches a layout file from a Cloudflare R2 bucket and passes it on (cached one day).
  - /api/track: looks up a SoundCloud audio track and redirects to its MP3 (not cached).
- In the visitor's browser it also calls Supabase (reads data; a feedback form writes to it) and Sefaria. That load falls on those services, not on our host.
- Growth is the main issue: 73 dafim are built so far, at about 270 KB each. All of the Talmud (about 2,700 dafim) would be roughly 700 MB of data files. The 2,269 sync files will also grow.
- Recommendation: keep AnyDaf Web on Vercel (or another host with CDN and serverless functions) for now. If it moves, put Cloudflare (free) in front and port the three functions.

## Bottom line
AnyMishnah Web adds almost no load and can go on the GoGeek account. AnyDaf Web is a different case and should not be moved without the function rewrite and a CDN.
