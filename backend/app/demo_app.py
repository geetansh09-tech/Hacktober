"""Synthetic 'Northwind Demo' shop. Mounted at /demo. Known behavior (ground truth for judges):
 - /catalog is client-rendered: product list is fetched from GET /demo/api/products
 - product page: 'Reviews' button -> GET /demo/api/products/{id}/reviews ; 'Add to cart' -> POST /demo/api/cart
 - /checkout redirects (302) to /login ; /admin returns 401 ; /help only linked from the footer
 - forms: POST /login, POST /register, POST /cart/coupon ; GET filter on catalog via fetch
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

demo = FastAPI(title="Northwind Demo (synthetic)")
P = "/demo"
PRODUCTS = [{"id": 1, "name": "Aurora Lamp", "category": "lighting", "price": 49},
            {"id": 2, "name": "Basalt Mug", "category": "kitchen", "price": 18},
            {"id": 3, "name": "Cirrus Throw", "category": "textiles", "price": 62}]


def page(title: str, body: str, script: str = "") -> HTMLResponse:
    nav = "".join(f'<a href="{P}{h}">{t}</a> ' for h, t in [("/", "Home"), ("/catalog", "Catalog"), ("/login", "Login")])
    html = f"""<!doctype html><html><head><meta charset=utf-8><title>{title}</title>
<meta name="generator" content="Northwind-Synthetic 1.0"></head>
<body style="font-family:sans-serif;max-width:720px;margin:2rem auto"><div id="demo-banner" style="background:#fef3c7;padding:6px">SYNTHETIC DEMO APP — not a real site</div>
<nav>{nav}</nav><main>{body}</main><footer><hr><a href="{P}/about">About</a> <a href="{P}/help">Help</a></footer>
<script>{script}</script></body></html>"""
    return HTMLResponse(html, headers={"X-Powered-By": "Northwind-Synthetic"})


@demo.get("/")
def home():
    return page("Northwind Demo — Home", f'<h1>Welcome to Northwind</h1><h2>Featured product</h2><a href="{P}/product/1">Aurora Lamp</a> <a href="{P}/cart">View cart</a>'
                '<p><button id="b">Subscribe tip</button></p>', "document.getElementById('b').onclick=()=>{document.getElementById('b').textContent='Thanks!'}")


@demo.get("/catalog")
def catalog():
    body = f'<h1>All products</h1><h2>Filters</h2><button id="f">Apply filters</button><ul id="list"><li>Loading…</li></ul><a href="{P}/cart">View cart</a>'
    js = f"""const load=(q)=>fetch('{P}/api/products'+(q||'')).then(r=>r.json()).then(d=>{{document.getElementById('list').innerHTML=d.map(p=>'<li><a href="{P}/product/'+p.id+'">'+p.name+'</a> $'+p.price+'</li>').join('')}});
load();document.getElementById('f').onclick=()=>load('?category=kitchen');"""
    return page("Catalog", body, js)


@demo.get("/product/{pid}")
def product(pid: int):
    p = next((x for x in PRODUCTS if x["id"] == pid), None)
    if not p:
        return HTMLResponse("Not found", status_code=404)
    body = f'<h1>{p["name"]}</h1><h2>Reviews</h2><div id="rev"></div><button id="r">Show reviews</button> <button id="a">Add to cart</button><p><a href="{P}/catalog">Back to catalog</a></p>'
    js = f"""document.getElementById('r').onclick=()=>fetch('{P}/api/products/{pid}/reviews').then(r=>r.json()).then(d=>{{document.getElementById('rev').textContent=d.length+' reviews'}});
document.getElementById('a').onclick=()=>fetch('{P}/api/cart',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id:{pid}}})}});"""
    return page(p["name"], body, js)


@demo.get("/cart")
def cart():
    return page("Your cart", f'<h1>Cart</h1><h2>Order summary</h2><form method="post" action="{P}/cart/coupon"><input name="coupon"><button type="submit">Apply coupon</button></form>'
                f'<a href="{P}/checkout">Checkout</a> <a href="{P}/catalog">Continue shopping</a>')


@demo.get("/login")
def login():
    return page("Sign in", f'<h1>Sign in</h1><form method="post" action="{P}/login"><input name="email"><input name="password" type="password"><button type="submit">Sign in</button></form><a href="{P}/register">Register</a>')


@demo.get("/register")
def register():
    return page("Create account", f'<h1>Create your account</h1><form method="post" action="{P}/register"><input name="name"><input name="email"><input name="password" type="password"><button type="submit">Register</button></form><a href="{P}/login">Sign in</a>')


@demo.get("/about")
def about():
    return page("About", f'<h1>About Northwind</h1><p>Synthetic demo company.</p><a href="{P}/admin">Staff area</a>')


@demo.get("/help")
def help_():
    return page("Help center", f'<h1>Help center</h1><h2>Shipping</h2><a href="{P}/catalog">Browse catalog</a>')


@demo.get("/checkout")
def checkout():
    return RedirectResponse(f"{P}/login", status_code=302)


@demo.get("/admin")
def admin():
    return HTMLResponse("Unauthorized", status_code=401)


@demo.get("/api/products")
def api_products(category: str | None = None):
    return [p for p in PRODUCTS if not category or p["category"] == category]


@demo.get("/api/products/{pid}/reviews")
def api_reviews(pid: int):
    return [{"user": "a", "stars": 5}, {"user": "b", "stars": 4}]


@demo.post("/api/cart")
def api_cart():
    return JSONResponse({"ok": True})


@demo.post("/login")
def post_login():
    return RedirectResponse(f"{P}/", status_code=303)


@demo.post("/register")
def post_register():
    return RedirectResponse(f"{P}/login", status_code=303)


@demo.post("/cart/coupon")
def post_coupon():
    return RedirectResponse(f"{P}/cart", status_code=303)
