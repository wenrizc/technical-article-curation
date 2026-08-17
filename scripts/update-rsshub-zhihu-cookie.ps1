param(
    [Parameter(Mandatory = $true)]
    [string]$Server,

    [string]$User = "root",

    [string]$RemoteDir = "/root/tech/technical-article-curation",

    [string]$ComposeFile = "compose.dev.yml",

    [string]$Cookie,

    [string]$CookieFile,

    [string]$TestRoute = "/zhihu/posts/people/youkaichao"
)

$ErrorActionPreference = "Stop"

if (-not $Cookie) {
    if ($CookieFile) {
        $Cookie = (Get-Content -LiteralPath $CookieFile -Raw).Trim()
    } else {
        $Cookie = Read-Host "Paste ZHIHU_COOKIES"
    }
}

if (-not $Cookie.Contains("z_c0=")) {
    throw "Cookie must contain z_c0="
}

if (-not $Cookie.Contains("d_c0=")) {
    throw "Cookie must contain d_c0="
}

$remote = "$User@$Server"
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Cookie))

$remoteScript = @"
set -eu
cd '$RemoteDir'
umask 077
python3 - <<'PY'
import base64
import os
import re
from pathlib import Path

path = Path("rsshub.env")
cookie = base64.b64decode("$encoded").decode("utf-8")
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
replacement = f"ZHIHU_COOKIES={cookie}"
pattern = re.compile(r"^\s*(?:export\s+)?ZHIHU_COOKIES\s*=")

for index, line in enumerate(lines):
    if pattern.match(line):
        lines[index] = replacement
        break
else:
    lines.append(replacement)

if not any(re.match(r"^\s*(?:export\s+)?CACHE_TYPE\s*=", line) for line in lines):
    lines.insert(0, "CACHE_TYPE=memory")

temporary = path.with_suffix(path.suffix + ".tmp")
temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
os.chmod(temporary, 0o600)
temporary.replace(path)
PY
docker compose -f '$ComposeFile' config --quiet
docker compose -f '$ComposeFile' up -d --force-recreate rsshub
for i in `$(seq 1 30); do
  if curl -fsS -m 3 http://127.0.0.1:1200/ >/tmp/rsshub_ready.html 2>/tmp/rsshub_ready.err; then
    break
  fi
  sleep 1
  if [ "`$i" = "30" ]; then
    echo "RSSHub did not become ready" >&2
    cat /tmp/rsshub_ready.err >&2 || true
    exit 1
  fi
done
curl -sS -m 30 -D /tmp/rsshub_zhihu_cookie_check.headers -o /tmp/rsshub_zhihu_cookie_check.body "http://127.0.0.1:1200$TestRoute" >/dev/null
status=`$(awk 'NR==1 {print `$2}' /tmp/rsshub_zhihu_cookie_check.headers)
if [ "`$status" = "200" ]; then
  echo "RSSHub Zhihu check passed: HTTP `$status"
else
  echo "RSSHub Zhihu check returned HTTP `$status"
  sed -n '1,20p' /tmp/rsshub_zhihu_cookie_check.headers
  python3 - <<'PY' || true
from pathlib import Path
import html, re
s = Path('/tmp/rsshub_zhihu_cookie_check.body').read_text(errors='ignore')
text = ' '.join(re.sub('<[^>]+>', ' ', html.unescape(s)).split())
print(text[:500])
PY
  exit 1
fi
"@

ssh $remote $remoteScript
