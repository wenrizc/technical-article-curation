// 自定义路由共享工具：RSS/Atom 抓取解析、HTML 列表页解析。
// 抓取优先使用 curl 子进程（经 PROXY_* 环境变量自动走宿主机代理），
// 绕开 Node undici TLS 与部分 trojan 节点链路的兼容问题；cheerio 用于解析。

import { spawn } from 'node:child_process';

import { load as cheerioLoad } from 'cheerio';

const cheerio = { load: cheerioLoad };

const DEFAULT_UA = 'Mozilla/5.0 (compatible; TAC-RSSHub/1.0)';

// 用 curl 子进程抓取（支持代理），失败时重试后回退 Node fetch。
async function fetchText(url, options = {}) {
    const retries = options.retries ?? 3;
    let lastError;
    for (let attempt = 0; attempt < retries; attempt++) {
        const args = ['-sSL', '--fail-with-body', '--max-time', String(options.timeoutSeconds || 30), '-A', options.ua || DEFAULT_UA, '--retry', '3', '--retry-delay', '1', '--retry-all-errors'];
        if (options.method && options.method !== 'GET') {
            args.push('-X', options.method);
        }
        if (options.body) {
            args.push('--data-binary', options.body);
        }
        const proxyEnv = {
            PROXY_PROTOCOL: process.env.PROXY_PROTOCOL,
            PROXY_HOST: process.env.PROXY_HOST,
            PROXY_PORT: process.env.PROXY_PORT,
            PROXY_AUTH: process.env.PROXY_AUTH,
        };
        if (proxyEnv.PROXY_HOST && proxyEnv.PROXY_PORT) {
            const auth = proxyEnv.PROXY_AUTH ? `${proxyEnv.PROXY_AUTH}@` : '';
            args.push('-x', `${proxyEnv.PROXY_PROTOCOL || 'http'}://${auth}${proxyEnv.PROXY_HOST}:${proxyEnv.PROXY_PORT}`);
        }
        if (options.headers) {
            for (const [k, v] of Object.entries(options.headers)) {
                args.push('-H', `${k}: ${v}`);
            }
        }
        try {
            return await spawnCollect('curl', [...args, url]);
        } catch (err) {
            lastError = err;
        }
    }
    // 回退 Node fetch（直连场景；代理节点 TLS 不兼容时仍可能失败）
    try {
        const resp = await fetch(url, {
            headers: {
                'User-Agent': options.ua || DEFAULT_UA,
                'Accept': 'application/rss+xml, application/atom+xml, text/html, application/xhtml+xml, */*;q=0.8',
                ...(options.headers || {}),
            },
            method: options.method || 'GET',
            body: options.body,
            redirect: 'follow',
            signal: AbortSignal.timeout((options.timeoutSeconds || 30) * 1000),
        });
        if (!resp.ok) {
            throw new Error(`fetch ${url} failed: ${resp.status}`);
        }
        return resp.text();
    } catch (err) {
        throw lastError || err;
    }
}

// spawn 收集 stdout，规避 execFile 大输出时的管道问题。
function spawnCollect(cmd, args) {
    return new Promise((resolve, reject) => {
        const child = spawn(cmd, args, { env: process.env });
        const chunks = [];
        child.stdout.on('data', (d) => chunks.push(d));
        child.on('error', reject);
        child.on('close', (code) => {
            if (code === 0) {
                resolve(Buffer.concat(chunks).toString('utf8'));
            } else {
                reject(new Error(`${cmd} exited with code ${code}`));
            }
        });
    });
}

// 解析 RSS 2.0 / Atom 为 item 列表。
// 使用 cheerio 读 XML，兼容两种格式；description 保留 HTML。
function parseFeed(xml, sourceUrl) {
    const $ = cheerio.load(xml, { xmlMode: true });
    const isAtom = !!$('feed').length;
    const items = [];
    if (isAtom) {
        $('feed > entry').each((_, el) => {
            const entry = $(el);
            const link = entry.find('link[rel="alternate"]').attr('href') || entry.find('link').first().attr('href') || '';
            const title = entry.find('title').first().text().trim();
            const published = entry.find('published').first().text().trim() || entry.find('updated').first().text().trim();
            let description = entry.find('content').first().text().trim();
            if (!description) {
                description = entry.find('summary').first().text().trim();
            }
            if (!title && !link) {
                return;
            }
            items.push({
                title: title || link,
                link,
                pubDate: published ? new Date(published) : undefined,
                description,
            });
        });
    } else {
        $('rss channel item, rss item').each((_, el) => {
            const item = $(el);
            const link = item.find('link').first().text().trim();
            const title = item.find('title').first().text().trim();
            const pubDate = item.find('pubDate').first().text().trim() || item.find('dc\\:date').first().text().trim();
            const description = item.find('description').first().html() || item.find('description').first().text();
            if (!title && !link) {
                return;
            }
            items.push({
                title: title || link,
                link,
                pubDate: pubDate ? new Date(pubDate) : undefined,
                description: description ? String(description).trim() : undefined,
            });
        });
    }
    return items;
}

// 通用代理：抓上游 feed 并转成 RSSHub 输出结构。
async function proxyFeed(sourceUrl, options = {}) {
    const xml = await fetchText(sourceUrl, options);
    const items = parseFeed(xml, sourceUrl);
    return {
        title: options.title || new URL(sourceUrl).hostname,
        link: options.siteUrl || sourceUrl,
        item: items,
    };
}

// 通用 HTML 列表页解析：linkSelector 选择文章链接，可选 titleSelector 取标题。
// excludeSelector + excludeValues 可在卡片内读取分类文本并按值跳过（如 Product/Monthly）。
async function parseListing(
    url,
    { linkSelector, titleSelector, baseUrl, urlPatterns = [], filter, excludeSelector, excludeValues = [], siteTitle }
) {
    const html = await fetchText(url);
    const $ = cheerio.load(html);
    const base = baseUrl || new URL(url).origin;
    const items = [];
    $(linkSelector).each((_, el) => {
        const node = $(el);
        const href = node.attr('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:')) {
            return;
        }
        const resolved = new URL(href, base).href;
        if (urlPatterns.length && !urlPatterns.some((p) => resolved.includes(p))) {
            return;
        }
        if (excludeSelector && excludeValues.length) {
            const category = node.find(excludeSelector).first().text().trim();
            if (excludeValues.includes(category)) {
                return;
            }
        }
        const title = titleSelector ? node.find(titleSelector).first().text().trim() : node.text().trim();
        if (!title && !resolved) {
            return;
        }
        if (filter && !filter(title, resolved)) {
            return;
        }
        items.push({ title: title || resolved, link: resolved });
    });
    return {
        title: siteTitle || new URL(url).hostname,
        link: url,
        item: items,
    };
}

export { fetchText, parseFeed, proxyFeed, parseListing };
