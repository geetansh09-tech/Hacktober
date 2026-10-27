// Client-side sanity check only. The backend performs the authoritative SSRF checks.
const PRIVATE = [
  /^localhost$/i, /\.local$/i, /\.internal$/i,
  /^127\./, /^10\./, /^192\.168\./, /^172\.(1[6-9]|2\d|3[01])\./,
  /^169\.254\./, /^0\./, /^\[?::1\]?$/, /^\[?f[cd][0-9a-f]{2}:/i,
];

export function validateTarget(raw: string): { ok: true; url: string } | { ok: false; reason: string } {
  const v = raw.trim();
  if (!v) return { ok: false, reason: "Enter a URL to analyze." };
  let u: URL;
  try { u = new URL(/^https?:\/\//i.test(v) ? v : `https://${v}`); }
  catch { return { ok: false, reason: "That doesn't look like a valid URL." }; }
  if (!["http:", "https:"].includes(u.protocol)) return { ok: false, reason: "Only http(s) URLs are allowed." };
  if (u.username || u.password) return { ok: false, reason: "URLs with embedded credentials are not allowed." };
  if (PRIVATE.some((r) => r.test(u.hostname)))
    return { ok: false, reason: "Localhost, private networks and metadata endpoints are blocked." };
  if (!u.hostname.includes(".") && !u.hostname.startsWith("[")) return { ok: false, reason: "Hostname must be a public domain." };
  return { ok: true, url: u.toString() };
}
