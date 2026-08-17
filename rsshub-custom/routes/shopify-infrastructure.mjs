// Shopify Infrastructure 主题。
// 上游：shopify.engineering/topics/infrastructure（无 RSS）。
// 文章卡片：article.article--index > a（标题即链接文本），需排除导航/功能链接。

import { fetchText } from './helpers.mjs';
import { load as cheerioLoad } from 'cheerio';

export const route = {
    path: '/shopify/infrastructure',
    categories: ['programming'],
    example: '/tac/shopify/infrastructure',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Shopify Infrastructure',
    maintainers: ['tac'],
    handler: async () => {
        const html = await fetchText('https://shopify.engineering/topics/infrastructure');
        const $ = cheerioLoad(html);
        const items = [];
        $('article a[href^="/"]').each((_, el) => {
            const node = $(el);
            const href = node.attr('href');
            const title = node.text().trim();
            if (!href || !title || title.length < 4 || href.startsWith('/topics') || href.startsWith('/authors') || href === '/') {
                return;
            }
            items.push({ title, link: new URL(href, 'https://shopify.engineering').href });
        });
        const seen = new Set();
        const unique = items.filter((it) => (seen.has(it.link) ? false : seen.add(it.link)));
        return {
            title: 'Shopify Engineering - Infrastructure',
            link: 'https://shopify.engineering/topics/infrastructure',
            item: unique,
        };
    },
};
