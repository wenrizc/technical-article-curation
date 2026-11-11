// Anthropic Engineering（Anthropic 工程博客）。
// 官方内置路由 /anthropic/engineering 返回 503，改为自建：
//   1. 抓 https://www.anthropic.com/engineering 列表页，卡片为 <article>，标题在 <h3><a href="/research/<slug>">。
//   2. 抓 sitemap.xml 建 "/research/<slug>" -> lastmod 映射，作为发布日期主营来源。
//   3. 兜底：解析卡片内的 "Nov 6, 2026" 文本日期。

import { load } from 'cheerio';

import { fetchText } from './helpers.mjs';

const BASE = 'https://www.anthropic.com';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function parseHumanDate(text) {
    const m = /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})/.exec(text || '');
    if (!m) {
        return undefined;
    }
    const month = MONTHS.indexOf(m[1]);
    if (month < 0) {
        return undefined;
    }
    const d = new Date(Date.UTC(Number(m[3]), month, Number(m[2]), 12, 0, 0));
    return Number.isNaN(d.getTime()) ? undefined : d;
}

async function sitemapDates() {
    const map = new Map();
    try {
        const xml = await fetchText(`${BASE}/sitemap.xml`, { timeoutSeconds: 40 });
        const re = /<loc>([^<]+)<\/loc>\s*(?:<lastmod>([^<]+)<\/lastmod>)?/g;
        let m = re.exec(xml);
        while (m !== null) {
            if (m[2]) {
                const d = new Date(m[2].trim());
                if (!Number.isNaN(d.getTime())) {
                    map.set(m[1].trim().replace(BASE, ''), d);
                }
            }
            m = re.exec(xml);
        }
    } catch {
        // sitemap 不可用时退回页面文本日期
    }
    return map;
}

export const route = {
    path: '/anthropic/engineering',
    categories: ['programming'],
    example: '/tac-custom/anthropic/engineering',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Anthropic Engineering',
    maintainers: ['tac'],
    handler: async () => {
        const [html, dates] = await Promise.all([fetchText(`${BASE}/engineering`, { timeoutSeconds: 40 }), sitemapDates()]);
        const $ = load(html);
        const seen = new Set();
        const item = [];
        $('article').each((_, el) => {
            const node = $(el);
            const anchor = node.find('h3 a').first();
            const href = (anchor.attr('href') || '').trim();
            const title = anchor.text().trim();
            if (!href.startsWith('/research/') || href.startsWith('/research/team/') || !title) {
                return;
            }
            if (seen.has(href)) {
                return;
            }
            seen.add(href);
            const pubDate = dates.get(href) || parseHumanDate(node.text());
            item.push({
                title,
                link: `${BASE}${href}`,
                pubDate,
                description: '',
            });
        });
        return {
            title: 'Anthropic Engineering',
            link: `${BASE}/engineering`,
            item,
        };
    },
};
