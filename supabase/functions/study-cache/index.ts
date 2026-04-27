import { serve } from "https://deno.land/std@0.168.0/http/server.ts"

const APP_SECRET       = Deno.env.get("APP_SECRET")!
const SUPABASE_URL     = Deno.env.get("SUPABASE_URL")!
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!

serve(async (req: Request) => {
  if (req.headers.get("x-app-secret") !== APP_SECRET) {
    return new Response("Unauthorized", { status: 401 })
  }

  const { searchParams } = new URL(req.url)

  if (req.method === "GET") {
    const key = searchParams.get("key")
    if (!key) return new Response("Missing key", { status: 400 })

    const url = `${SUPABASE_URL}/rest/v1/study_cache`
      + `?key=eq.${key}&select=summary,questions_json,shiur_used&limit=1`

    const response = await fetch(url, {
      headers: {
        "apikey":        SERVICE_ROLE_KEY,
        "Authorization": `Bearer ${SERVICE_ROLE_KEY}`,
      },
    })
    return new Response(await response.text(), {
      status: response.status,
      headers: { "content-type": "application/json" },
    })
  }

  if (req.method === "POST") {
    const onConflict = searchParams.get("on_conflict")
    const prefer     = req.headers.get("Prefer") ?? "resolution=ignore-duplicates"
    const body       = await req.text()

    let url = `${SUPABASE_URL}/rest/v1/study_cache`
    if (onConflict) url += `?on_conflict=${onConflict}`

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "apikey":        SERVICE_ROLE_KEY,
        "Authorization": `Bearer ${SERVICE_ROLE_KEY}`,
        "Content-Type":  "application/json",
        "Prefer":        prefer,
      },
      body,
    })
    return new Response(null, { status: response.status })
  }

  return new Response("Method not allowed", { status: 405 })
})
