param(
    [Parameter(Mandatory = $true)]
    [string]$Server,

    [string]$User = "root",

    [string]$RemoteDir = "/root/tech/technical-article-curation",

    [string]$ComposeFile = "compose.dev.yml",

    [string]$TestRoute = "/zhihu/posts/people/youkaichao",

    [string]$ProfileDir = "$PSScriptRoot\.zhihu-playwright-profile",

    [string]$WorkDir = "$env:LOCALAPPDATA\rsshub-zhihu-cookie-updater",

    [int]$LoginTimeoutSeconds = 300,

    [switch]$SkipRemoteUpdate,

    [switch]$KeepBrowserOpen
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Require-Command "node"
Require-Command "npm"
Require-Command "ssh"

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null

$packageJson = Join-Path $WorkDir "package.json"
if (-not (Test-Path -LiteralPath $packageJson)) {
    @'
{"private":true,"dependencies":{"playwright":"latest"}}
'@ | Set-Content -LiteralPath $packageJson -Encoding UTF8
}

Push-Location $WorkDir
try {
    if (-not (Test-Path -LiteralPath (Join-Path $WorkDir "node_modules\playwright"))) {
        npm install
    }
    npx playwright install chromium
} finally {
    Pop-Location
}

$helper = Join-Path $WorkDir "login-zhihu-export-cookie.cjs"
@'
const { chromium } = require('playwright');

const profileDir = process.env.ZHIHU_PROFILE_DIR;
const timeoutSeconds = Number(process.env.ZHIHU_LOGIN_TIMEOUT_SECONDS || '300');
const keepBrowserOpen = process.env.ZHIHU_KEEP_BROWSER_OPEN === '1';

const requiredNames = new Set(['z_c0', 'd_c0']);
const preferredOrder = [
  '_xsrf',
  '_zap',
  'd_c0',
  'q_c1',
  'z_c0',
  'Hm_lvt_98beee57fd2ef70ccdd5ca52b9740c49',
  'HMACCOUNT',
  '__zse_ck',
  'SESSIONID',
  'JOID',
  'osd',
  'Hm_lpvt_98beee57fd2ef70ccdd5ca52b9740c49',
  'BEC',
];

function cookieHeader(cookies) {
  const zhihuCookies = cookies.filter((cookie) => {
    const domain = cookie.domain.replace(/^\./, '');
    return domain === 'zhihu.com' || domain.endsWith('.zhihu.com');
  });

  const byName = new Map();
  for (const cookie of zhihuCookies) {
    if (!byName.has(cookie.name) || cookie.expires > byName.get(cookie.name).expires) {
      byName.set(cookie.name, cookie);
    }
  }

  const names = [
    ...preferredOrder.filter((name) => byName.has(name)),
    ...[...byName.keys()].filter((name) => !preferredOrder.includes(name)).sort(),
  ];

  return names.map((name) => `${name}=${byName.get(name).value}`).join('; ');
}

async function main() {
  if (!profileDir) {
    throw new Error('ZHIHU_PROFILE_DIR is required');
  }

  const context = await chromium.launchPersistentContext(profileDir, {
    headless: false,
    viewport: { width: 1280, height: 900 },
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
  });

  const page = context.pages()[0] || await context.newPage();
  await page.goto('https://www.zhihu.com/signin?next=%2F', { waitUntil: 'domcontentloaded' });

  console.error('Browser opened. Log in to Zhihu in the browser window.');
  console.error(`Waiting up to ${timeoutSeconds} seconds for z_c0 and d_c0 cookies...`);

  const deadline = Date.now() + timeoutSeconds * 1000;
  let cookies = [];
  while (Date.now() < deadline) {
    cookies = await context.cookies(['https://www.zhihu.com']);
    const names = new Set(cookies.map((cookie) => cookie.name));
    const ready = [...requiredNames].every((name) => names.has(name));
    if (ready) {
      break;
    }
    await page.waitForTimeout(2000);
  }

  cookies = await context.cookies(['https://www.zhihu.com']);
  const names = new Set(cookies.map((cookie) => cookie.name));
  const missing = [...requiredNames].filter((name) => !names.has(name));
  if (missing.length) {
    throw new Error(`Login did not produce required cookies: ${missing.join(', ')}`);
  }

  const header = cookieHeader(cookies);
  if (!header.includes('z_c0=') || !header.includes('d_c0=')) {
    throw new Error('Exported cookie header is missing z_c0 or d_c0');
  }

  const apiResponse = await page.request.get('https://www.zhihu.com/api/v4/me?include=is_realname', {
    headers: {
      Cookie: header,
      Referer: 'https://www.zhihu.com/',
    },
    timeout: 30000,
  });

  if (!apiResponse.ok()) {
    console.error(`Warning: Zhihu /api/v4/me returned HTTP ${apiResponse.status()}`);
  } else {
    try {
      const body = await apiResponse.json();
      if (body && body.name) {
        console.error(`Zhihu login detected as: ${body.name}`);
      }
    } catch {
      console.error('Warning: Zhihu /api/v4/me response was not JSON');
    }
  }

  console.log(header);

  if (!keepBrowserOpen) {
    await context.close();
  } else {
    console.error('Keeping browser open. Close it manually when done.');
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
'@ | Set-Content -LiteralPath $helper -Encoding UTF8

$cookieFile = Join-Path $WorkDir "zhihu-cookie.txt"
$env:ZHIHU_PROFILE_DIR = (Resolve-Path -LiteralPath $ProfileDir).Path
$env:ZHIHU_LOGIN_TIMEOUT_SECONDS = [string]$LoginTimeoutSeconds
$env:ZHIHU_KEEP_BROWSER_OPEN = if ($KeepBrowserOpen) { "1" } else { "0" }

Push-Location $WorkDir
try {
    node $helper | Tee-Object -FilePath $cookieFile | Out-Null
} finally {
    Pop-Location
}

$cookie = (Get-Content -LiteralPath $cookieFile -Raw).Trim()
if (-not $cookie.Contains("z_c0=")) {
    throw "Exported cookie must contain z_c0="
}
if (-not $cookie.Contains("d_c0=")) {
    throw "Exported cookie must contain d_c0="
}

Write-Host "Exported Zhihu cookie to $cookieFile"

if ($SkipRemoteUpdate) {
    Write-Host "Skipping remote update because -SkipRemoteUpdate was set."
    exit 0
}

$remote = "$User@$Server"
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($cookie))

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
curl -sS -m 60 -D /tmp/rsshub_zhihu_cookie_check.headers -o /tmp/rsshub_zhihu_cookie_check.body "http://127.0.0.1:1200$TestRoute" >/dev/null
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
print(text[:700])
PY
  exit 1
fi
"@

ssh $remote $remoteScript
