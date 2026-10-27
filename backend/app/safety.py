"""SSRF / destination safety. Used for the target URL AND for every browser request + redirect hop."""
import asyncio, ipaddress, socket
from urllib.parse import urlsplit

BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal", "instance-data", "kubernetes.default"}
BLOCKED_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home.arpa", ".corp")
ALLOWED_PORTS = {80, 443, 8080, 8443}


class UnsafeURL(ValueError):
    pass


def ip_is_public(ip: str) -> bool:
    a = ipaddress.ip_address(ip.split("%")[0])
    if getattr(a, "ipv4_mapped", None):
        a = a.ipv4_mapped
    return a.is_global and not a.is_multicast


def origin_of(url: str) -> str:
    s = urlsplit(url)
    return f"{s.scheme}://{s.netloc}".lower()


def root_domain(url_or_host: str) -> str:
    if "://" in url_or_host:
        h = urlsplit(url_or_host).hostname or ""
    else:
        h = url_or_host
    parts = h.rstrip(".").lower().split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return h.lower()


def same_registered_domain(u1: str, u2: str) -> bool:
    r1, r2 = root_domain(u1), root_domain(u2)
    return bool(r1 and r2 and r1 == r2)


def check_syntax(url: str):
    """Pure (no DNS) validation. Returns the SplitResult or raises UnsafeURL."""
    if not isinstance(url, str) or len(url) > 2048:
        raise UnsafeURL("URL missing or too long")
    s = urlsplit(url.strip())
    if s.scheme not in ("http", "https"):
        raise UnsafeURL("Only http(s) URLs are allowed")
    if s.username or s.password:
        raise UnsafeURL("Embedded credentials are not allowed")
    host = (s.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeURL("URL has no hostname")
    try:
        port = s.port
    except ValueError:
        raise UnsafeURL("Invalid port")
    if port is not None and port not in ALLOWED_PORTS:
        raise UnsafeURL(f"Port {port} is not allowed")
    if host in BLOCKED_HOSTS or host.endswith(BLOCKED_SUFFIXES):
        raise UnsafeURL("Internal hostnames are blocked")
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip:
        if not ip_is_public(host):
            raise UnsafeURL("Private, loopback, link-local or metadata addresses are blocked")
    elif "." not in host:
        raise UnsafeURL("Hostname must be a public domain")
    return s


class UrlChecker:
    """Resolves DNS and requires ALL answers to be public. `allowed_origin` is a single exact
    exception used only for the bundled demo app."""

    def __init__(self, allowed_origin: str | None = None):
        self.allowed_origin = allowed_origin.lower() if allowed_origin else None
        self._cache: dict[str, str | None] = {}

    async def check(self, url: str):
        if self.allowed_origin and origin_of(url) == self.allowed_origin:
            return
        s = check_syntax(url)
        host = s.hostname.rstrip(".").lower()
        if host not in self._cache:
            try:
                ipaddress.ip_address(host)
                self._cache[host] = None
            except ValueError:
                try:
                    infos = await asyncio.get_running_loop().getaddrinfo(host, s.port or 443, type=socket.SOCK_STREAM)
                except socket.gaierror:
                    raise UnsafeURL("Hostname could not be resolved")
                bad = [i[4][0] for i in infos if not ip_is_public(i[4][0])]
                self._cache[host] = f"resolves to non-public address {bad[0]}" if bad or not infos else None
        if self._cache[host]:
            raise UnsafeURL(f"Blocked: {host} {self._cache[host]}")
