import asyncio, pytest
from app.safety import UnsafeURL, UrlChecker, check_syntax, ip_is_public

BAD = ["http://localhost/", "http://127.0.0.1/", "http://10.0.0.1/", "http://192.168.1.5/", "http://172.16.0.1/", "http://169.254.169.254/latest/meta-data",
       "http://metadata.google.internal/", "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://2130706433/", "http://0x7f.0.0.1/", "http://user:pw@example.com/",
       "ftp://example.com/", "file:///etc/passwd", "http://example.com:22/", "http://intranet/", "http://printer.local/", "http://100.64.0.1/"]


@pytest.mark.parametrize("u", BAD)
def test_blocked_syntax_or_ip(u):
    with pytest.raises(UnsafeURL):
        asyncio.run(UrlChecker().check(u))


def test_public_ip_literal_ok():
    check_syntax("https://93.184.216.34/")
    assert ip_is_public("8.8.8.8") and not ip_is_public("fd00::1")


def test_demo_exception_is_exact_origin_only():
    c = UrlChecker(allowed_origin="http://127.0.0.1:8000")
    asyncio.run(c.check("http://127.0.0.1:8000/demo/"))
    with pytest.raises(UnsafeURL):
        asyncio.run(c.check("http://127.0.0.1:9999/"))
    with pytest.raises(UnsafeURL):
        asyncio.run(c.check("http://169.254.169.254/"))
