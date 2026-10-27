import type { Analysis, PageObs } from "../types";

// UI PREVIEW FIXTURE — hand-written sample so the dashboard can be viewed before the backend exists.
// It is NEVER shown as a real analysis: `fixture: true` triggers a visible banner and report watermark.
const pg = (id: string, path: string, title: string, headings: string[], buttons: string[], links: [string, string][], forms: PageObs["forms"] = []): PageObs => ({
  id, path, title, url: `https://demo.invalid${path}`, status_code: 200, headings, buttons, forms,
  links: links.map(([text, href]) => ({ text, href })),
});

export const fixtureAnalysis = (): Analysis => ({
  id: "fixture", target_url: "https://demo.invalid/", status: "completed", demo: true, fixture: true,
  started_at: new Date().toISOString(), elapsed_s: 12.4, limits: { max_pages: 25, time_limit_s: 120 },
  progress: { pages_discovered: 6, pages_visited: 6, message: "Fixture loaded" }, engine: "rules",
  pages: [
    pg("p0", "/", "Northwind Demo — Home", ["Welcome to Northwind", "Featured products"], ["Add to cart", "Search"], [["Catalog", "/catalog"], ["Login", "/login"], ["Cart", "/cart"]]),
    pg("p1", "/catalog", "Catalog", ["All products", "Filters"], ["Add to cart", "Apply filters"], [["Product #1", "/product/1"], ["Cart", "/cart"]], [{ action: "/catalog", method: "get", fields: ["q", "category", "sort"] }]),
    pg("p2", "/login", "Sign in", ["Sign in"], ["Sign in"], [["Register", "/register"]], [{ action: "/login", method: "post", fields: ["email", "password"] }]),
    pg("p3", "/product/1", "Product detail", ["Aurora Lamp", "Reviews"], ["Add to cart", "Write review"], [["Back to catalog", "/catalog"]]),
    pg("p4", "/cart", "Your cart", ["Cart", "Order summary"], ["Checkout", "Remove"], [["Continue shopping", "/catalog"]], [{ action: "/checkout", method: "post", fields: ["coupon"] }]),
    pg("p5", "/register", "Create account", ["Create your account"], ["Register"], [["Sign in", "/login"]], [{ action: "/register", method: "post", fields: ["name", "email", "password"] }]),
  ],
  edges: [
    { id: "e0", source: "p0", target: "p1", provenance: "observed", action: "click link 'Catalog'", evidence: ["<a href=/catalog> clicked; URL changed to /catalog"] },
    { id: "e1", source: "p0", target: "p2", provenance: "observed", action: "click link 'Login'", evidence: ["<a href=/login> clicked"] },
    { id: "e2", source: "p0", target: "p4", provenance: "observed", action: "click link 'Cart'", evidence: ["<a href=/cart> clicked"] },
    { id: "e3", source: "p1", target: "p3", provenance: "observed", action: "click link 'Product #1'", evidence: ["<a href=/product/1> clicked"] },
    { id: "e4", source: "p2", target: "p5", provenance: "observed", action: "click link 'Register'", evidence: ["<a href=/register> clicked"] },
    { id: "e5", source: "p3", target: "p4", provenance: "inferred", action: "'Add to cart' button → cart", evidence: ["Button 'Add to cart' present on /product/1", "Cart page exists at /cart", "Click not executed (state-changing action skipped)"] },
    { id: "e6", source: "p4", target: "p2", provenance: "inferred", action: "Checkout likely requires auth", evidence: ["Cart has 'Checkout' button", "Login page exists", "No observation of the redirect itself"] },
  ],
  hypotheses: [
    { id: "h0", category: "module", title: "Product catalog & search", description: "A listing page with a GET form (q, category, sort) and product detail routes suggests server- or client-side filtering over a product collection.", provenance: "observed", confidence: "high", evidence: ["/catalog form GET [q, category, sort]", "/product/1 reached from /catalog"] },
    { id: "h1", category: "module", title: "Authentication", description: "Login and registration pages with POST forms and password fields indicate an account system.", provenance: "observed", confidence: "high", evidence: ["/login POST [email, password]", "/register POST [name, email, password]"] },
    { id: "h2", category: "workflow", title: "Browse → product → cart → checkout", description: "Link graph and button labels outline a classic purchase funnel. The final checkout step was not exercised.", provenance: "inferred", confidence: "medium", evidence: ["p1→p3 observed", "'Add to cart' on /product/1", "'Checkout' on /cart"] },
    { id: "h3", category: "architecture", title: "Server-rendered multi-page app", description: "Navigation caused full URL changes with distinct titles per route, consistent with MPA rendering. A SPA with client routing would look similar from links alone.", provenance: "inferred", confidence: "low", evidence: ["Distinct <title> per page", "Link clicks changed location"] },
    { id: "h4", category: "architecture", title: "Session/cookie-based auth backend", description: "Credential POST forms are typical of a session handler. Token-based or third-party auth cannot be excluded.", provenance: "inferred", confidence: "low", evidence: ["POST form on /login with password field"] },
  ],
  missing_info: ["No authenticated pages were explored (auth is never bypassed).", "State-changing actions (add to cart, submit forms) were not executed.", "Network/API calls were not captured in this fixture."],
  next_experiments: ["Capture XHR/fetch endpoints during navigation to confirm client/server split.", "Compare response headers across routes to identify frameworks or CDN.", "Run again with a larger page limit to reach deeper product routes."],
});
