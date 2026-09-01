// 前端统一通过 /api/proxy 访问后端（服务端转发，浏览器不接触 API Key）
const PROXY = "/api/proxy";

export async function apiGet<T = any>(path: string): Promise<T> {
  const r = await fetch(`${PROXY}${path}`);
  if (!r.ok) throw new Error(`请求失败 ${r.status}: ${await safeText(r)}`);
  return r.json();
}

export async function apiPost<T = any>(path: string, body?: any): Promise<T> {
  const r = await fetch(`${PROXY}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`请求失败 ${r.status}: ${await safeText(r)}`);
  return r.json();
}

export async function apiPatch<T = any>(path: string, body?: any): Promise<T> {
  const r = await fetch(`${PROXY}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`请求失败 ${r.status}: ${await safeText(r)}`);
  return r.json();
}

export async function apiUploadFiles(files: File[]): Promise<any[]> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  const r = await fetch(`${PROXY}/papers/batch-upload`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(`上传失败 ${r.status}: ${await safeText(r)}`);
  return r.json();
}

export function fileUrl(key: string): string {
  return `${PROXY}/files/${encodeURIComponent(key)}`;
}

async function safeText(r: Response): Promise<string> {
  try {
    const t = await r.text();
    return t.slice(0, 200);
  } catch {
    return "";
  }
}

export async function streamChat(
  body: { message: string; paper_id?: string | null; skill?: string | null; history?: any[] },
  onDelta: (text: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const r = await fetch(`${PROXY}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok || !r.body) throw new Error(`Chat 失败 ${r.status}`);
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const s = line.trim();
      if (!s.startsWith("data:")) continue;
      const payload = JSON.parse(s.slice(5).trim());
      if (payload.delta) onDelta(payload.delta);
    }
  }
}

export async function streamAgent(
  message: string,
  onDelta: (text: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const r = await fetch(`${PROXY}/agent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!r.ok || !r.body) throw new Error(`Agent 失败 ${r.status}`);
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const s = line.trim();
      if (!s.startsWith("data:")) continue;
      const payload = JSON.parse(s.slice(5).trim());
      if (payload.delta) onDelta(payload.delta);
    }
  }
}
