import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

function stripHopHeaders(headers: Headers) {
  const out = new Headers();
  headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (["content-length", "transfer-encoding", "connection", "host", "keep-alive"].includes(k)) return;
    out.set(key, value);
  });
  return out;
}

async function handler(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
) {
  const { path: pathSegments } = await ctx.params;
  const path = (pathSegments || []).join("/");
  const url = `${BACKEND_URL}/api/v1/${path}${req.nextUrl.search}`;

  const headers = new Headers();
  if (process.env.PAPERHUB_API_KEY) {
    headers.set("Authorization", `Bearer ${process.env.PAPERHUB_API_KEY}`);
  }
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (req.headers.get("accept")) headers.set("accept", req.headers.get("accept")!);

  let body: BodyInit | null = null;
  if (req.method !== "GET" && req.method !== "HEAD") {
    if (contentType && contentType.includes("multipart/form-data")) {
      body = await req.arrayBuffer();
    } else {
      body = await req.text();
    }
  }

  try {
    const upstream = await fetch(url, {
      method: req.method,
      headers,
      body,
      // @ts-ignore
      duplex: body ? "half" : undefined,
    });

    const respHeaders = stripHopHeaders(upstream.headers);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: respHeaders,
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ detail: `无法连接后端: ${String(err)}` }),
      { status: 502, headers: { "content-type": "application/json" } }
    );
  }
}

export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE };
