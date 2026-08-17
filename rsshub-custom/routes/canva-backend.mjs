// Canva Engineering - Backend tag。
// 上游：www.canva.dev/blog/engineering/tag/backend/（无 RSS）。
// 文章卡片：<a href="/blog/engineering/.../"> 内包含 <h4> 标题。

import { fetchText } from './helpers.mjs';
import { load as cheerioLoad } from 'cheerio';

function makeHandler(tag, title, pageUrl) {
    return async () => {
        const html = await fetchText(pageUrl);
        const $ = cheerioLoad(html);
        const items = [];
        $('a[href*="/blog/engineering/"]').each((_, el) => {
            const node = $(el);
            const href = node.attr('href');
            const h = node.find('h4, h3, h2').first().text().trim();
            if (!href || !h || href === '/blog/engineering/') {
                return;
            }
            items.push({ title: h, link: new URL(href, 'https://www.canva.dev').href });
        });
        const seen = new Set();
        const unique = items.filter((it) => (seen.has(it.link) ? false : seen.add(it.link)));
        return {
            title,
            link: pageUrl,
            item: unique,
        };
    };
}

export const route = {
    path: '/canva/backend',
    categories: ['programming'],
    example: '/tac/canva/backend',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Canva Engineering - Backend',
    maintainers: ['tac'],
    handler: makeHandler('Backend', 'Canva Engineering - Backend', 'https://www.canva.dev/blog/engineering/tag/backend/'),
};
