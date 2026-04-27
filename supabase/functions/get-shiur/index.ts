import { serve } from "https://deno.land/std@0.168.0/http/server.ts"

// APP_SECRET must be set via: supabase secrets set APP_SECRET=...
// SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are auto-injected by Supabase.
const APP_SECRET           = Deno.env.get("APP_SECRET")!
const SUPABASE_URL         = Deno.env.get("SUPABASE_URL")!
const SERVICE_ROLE_KEY     = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!

serve(async (req: Request) => {
  if (req.method !== "GET") {
    return new Response("Method not allowed", { status: 405 })
  }

  // Same secret-header pattern as claude-proxy.
  if (req.headers.get("x-app-secret") !== APP_SECRET) {
    return new Response("Unauthorized", { status: 401 })
  }

  const { searchParams } = new URL(req.url)
  const tractate = searchParams.get("tractate")
  const daf      = searchParams.get("daf")

  if (!tractate || !daf) {
    return new Response("Missing tractate or daf", { status: 400 })
  }

  // Use the service role key so this works after anon SELECT is removed from RLS.
  const url = `${SUPABASE_URL}/rest/v1/shiur_content`
    + `?tractate=eq.${encodeURIComponent(tractate)}`
    + `&daf=eq.${daf}`
    + `&select=segmentation,rewrite,final`

  const response = await fetch(url, {
    headers: {
      "apikey":        SERVICE_ROLE_KEY,
      "Authorization": `Bearer ${SERVICE_ROLE_KEY}`,
    },
  })

  const body = await response.text()
  return new Response(body, {
    status: response.status,
    headers: { "content-type": "application/json" },
  })
})
