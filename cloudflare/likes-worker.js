// WallSpotter like counter — Cloudflare Worker (needs a KV binding named LIKES).
// GET  /likes?ids=a,b,c   -> {"a":3,"b":0,"c":12}
// POST /like  {"id":"a","action":"like"|"unlike"} -> {"id":"a","count":4,"liked":true}
const ORIGINS = ["https://www.wallspotter.com", "https://wallspotter.com"];
const SALT = "wallspotter-likes-v1";
const ID_RE = /^[a-z0-9-]{1,80}$/;
const VOTE_TTL = 60 * 60 * 24 * 365; // one vote per visitor per wallpaper, remembered for a year

function cors(req) {
  const o = req.headers.get("Origin");
  return {
    "Access-Control-Allow-Origin": ORIGINS.includes(o) ? o : ORIGINS[0],
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}

function json(req, data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...cors(req) },
  });
}

async function voterKey(req, id) {
  // visitor fingerprint is hashed; no IP address is stored
  const ip = req.headers.get("CF-Connecting-IP") || "0";
  const data = new TextEncoder().encode(`${SALT}|${ip}|${id}`);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return "v:" + [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 40);
}

async function getCount(env, id) {
  return parseInt((await env.LIKES.get("c:" + id)) || "0", 10);
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method === "OPTIONS") return new Response(null, { headers: cors(req) });

    if (req.method === "GET" && url.pathname === "/likes") {
      const ids = (url.searchParams.get("ids") || "").split(",").filter((i) => ID_RE.test(i)).slice(0, 60);
      const out = {};
      await Promise.all(ids.map(async (id) => { out[id] = await getCount(env, id); }));
      return json(req, out);
    }

    if (req.method === "POST" && url.pathname === "/like") {
      let body;
      try { body = await req.json(); } catch { return json(req, { error: "bad request" }, 400); }
      const id = String(body.id || "");
      const action = body.action === "unlike" ? "unlike" : "like";
      if (!ID_RE.test(id)) return json(req, { error: "bad id" }, 400);

      const vk = await voterKey(req, id);
      const voted = (await env.LIKES.get(vk)) !== null;
      let count = await getCount(env, id);

      if (action === "like" && !voted) {
        count += 1;
        await env.LIKES.put("c:" + id, String(count));
        await env.LIKES.put(vk, "1", { expirationTtl: VOTE_TTL });
      } else if (action === "unlike" && voted) {
        count = Math.max(0, count - 1);
        await env.LIKES.put("c:" + id, String(count));
        await env.LIKES.delete(vk);
      }
      return json(req, { id, count, liked: action === "like" });
    }

    return json(req, { error: "not found" }, 404);
  },
};
