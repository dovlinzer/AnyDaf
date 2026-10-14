// Shared-password gate for a static Vercel site (HTTP Basic Auth, runs before every request, including /api).
// The password is NOT in this file: set it as the environment variable SITE_PASSWORD in the Vercel project.
// Any username is accepted; only the password is checked. If SITE_PASSWORD is not set the site stays locked (fails closed).
export const config = { matcher: "/:path*" };

function same(a, b) {
  // constant-time comparison, so response time does not leak how many characters matched
  const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b);
  let d = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) d |= (x[i] || 0) ^ (y[i] || 0);
  return d === 0;
}

export default function middleware(request) {
  const password = process.env.SITE_PASSWORD;
  if (!password) return new Response("This site is locked: SITE_PASSWORD is not set.", { status: 503 });
  const header = request.headers.get("authorization") || "";
  if (header.startsWith("Basic ")) {
    try {
      const decoded = atob(header.slice(6));
      const given = decoded.slice(decoded.indexOf(":") + 1);
      if (same(given, password)) return new Response(null, { headers: { "x-middleware-next": "1" } }); // let the request through
    } catch (e) { /* malformed header: fall through to the prompt */ }
  }
  return new Response("Password required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Private preview", charset="UTF-8"', "Cache-Control": "no-store" },
  });
}
