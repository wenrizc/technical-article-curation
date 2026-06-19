from tac.fetch import fetch_url


class FakeResponse:
    status_code = 200
    url = "https://example.com/article"
    encoding = "utf-8"
    apparent_encoding = "utf-8"
    text = "<html><body><article><h1>Title</h1><p>Body</p></article></body></html>"

    def raise_for_status(self):
        return None


class FakeSession:
    last_headers = None

    def __init__(self):
        self.headers = {}

    def get(self, url, timeout, allow_redirects):
        FakeSession.last_headers = dict(self.headers)
        assert timeout == (10, 30)
        assert allow_redirects is True
        return FakeResponse()


def test_fetch_url_can_disable_crawler4ai_and_use_requests_fallback(monkeypatch):
    def fail_if_called(url):
        raise AssertionError("crawler4ai should not be called when disabled")

    monkeypatch.setattr("tac.fetch._fetch_with_crawler4ai", fail_if_called)
    monkeypatch.setattr("tac.fetch.requests.Session", FakeSession)

    result = fetch_url("https://example.com/article", crawler4ai_enabled=False)

    assert result.metadata["crawler"] == "requests+beautifulsoup+markdownify"
    assert "Mozilla/5.0" in FakeSession.last_headers["User-Agent"]
    assert "Title" in result.markdown

