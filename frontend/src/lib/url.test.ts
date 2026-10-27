import { describe, it, expect } from "vitest";
import { validateTarget } from "./url";

describe("validateTarget", () => {
  it("accepts public urls and adds scheme", () => {
    const r = validateTarget("example.com");
    expect(r.ok && r.url).toBe("https://example.com/");
  });
  it.each(["http://localhost:3000", "http://127.0.0.1", "http://10.0.0.5", "http://169.254.169.254/latest", "http://192.168.1.1", "http://172.20.0.1", "http://[::1]/"])(
    "blocks %s", (u) => expect(validateTarget(u).ok).toBe(false));
  it("blocks credentials and non-http schemes", () => {
    expect(validateTarget("https://user:pw@example.com").ok).toBe(false);
    expect(validateTarget("ftp://example.com").ok).toBe(false);
  });
  it("rejects empty input", () => expect(validateTarget("  ").ok).toBe(false));
});
