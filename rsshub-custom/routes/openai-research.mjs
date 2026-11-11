// OpenAI Research。
// 内置路由 /openai/research 会逐条抓 https://openai.com/index/<slug>/ 详情页，被 403 拦死（503）。
// 改为直接消费官方 RSS https://openai.com/news/rss.xml（1380 条、带 category、带 pubDate），
// 只保留研究/发布类标签的条目。

import { load } from 'cheerio';

import { fetchText } from './helpers.mjs';

const FEED = 'https://openai.com/news/rss.xml';
const SITE = 'https://openai.com/news/';
const KEEP = new Set([
    'research',
    'publication',
    'engineering',
    'safety & alignment',
    'security',
    'safety',
]);

export const route = {
    path: '/openai/research',
    categories: ['programming'],
    example: '/tac-custom/openai/research',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'OpenAI Research',
    maintainers: ['tac'],
    handler: async () => {
        const xml = await fetchText(FEED, { timeoutSeconds: 60 });
        const $ = load(xml, { xmlMode: true });
        const item = [];
        $('item').each((_, el) => {
            const node = $(el);
            const cats = node
                .find('category')
                .map((__, c) => $(c).text().trim().toLowerCase())
                .get();
            if (!cats.some((c) => KEEP.has(c))) {
                return;
            }
            const link = node.find('link').first().text().trim();
            const title = node.find('title').first().text().trim();
            if (!link || !title) {
                return;
            }
            const raw = node.find('pubDate').first().text().trim();
            const pub = raw ? new Date(raw) : undefined;
            item.push({
                title,
                link,
                pubDate: pub && !Number.isNaN(pub.getTime()) ? pub : undefined,
                description: '',
            });
        });
        item.sort((a, b) => (b.pubDate ? b.pubDate.getTime() : 0) - (a.pubDate ? a.pubDate.getTime() : 0));
        return {
            title: 'OpenAI Research',
            link: SITE,
            item: item.slice(0, 80),
        };
    },
};
