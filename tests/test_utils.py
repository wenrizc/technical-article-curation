from tac.utils import normalize_url, source_title_slug


def test_normalize_url_removes_tracking_and_default_port():
    assert (
        normalize_url("HTTPS://Example.com:443/a//b/?utm_source=x&b=2&a=1#frag")
        == "https://example.com/a/b?a=1&b=2"
    )


def test_slug_collision_adds_hash():
    slug = source_title_slug(
        "Cloudflare", "How We Debugged X", "https://example.com/x", exists=True
    )
    assert slug.startswith("cloudflare-how-we-debugged-x-")
    assert len(slug.rsplit("-", 1)[-1]) == 8
