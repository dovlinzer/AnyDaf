import { serve } from "https://deno.land/std@0.168.0/http/server.ts"

// These are set as Supabase secrets (supabase secrets set ...) and never
// leave the server — they are not visible in this source file at runtime.
const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY")!
const APP_SECRET        = Deno.env.get("APP_SECRET")!
const ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"

serve(async (req: Request) => {
  // Only POST is supported
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 })
  }

  // Validate the app secret sent by the client app.
  // This prevents anyone who discovers the function URL from using it freely.
  if (req.headers.get("x-app-secret") !== APP_SECRET) {
    return new Response("Unauthorized", { status: 401 })
  }

  // Forward the request body to Anthropic unchanged.
  // The app builds the full messages payload; the proxy just adds the API key.
  const body = await req.text()

  const anthropicResponse = await fetch(ANTHROPIC_URL, {
    method: "POST",
    headers: {
      "x-api-key":         ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type":      "application/json",
    },
    body,
  })

  // Return Anthropic's response (including status code) directly to the app.
  // 429 rate-limit responses pass through unchanged so the app's retry logic works.
  const responseText = await anthropicResponse.text()
  return new Response(responseText, {
    status: anthropicResponse.status,
    headers: { "content-type": "application/json" },
  })
})
