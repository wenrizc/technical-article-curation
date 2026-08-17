// Canva Engineering - Infrastructure tag。
// 上游：www.canva.dev/blog/engineering/tag/infrastructure/（无 RSS）。
// 文章卡片：<a href="/blog/engineering/.../"> 内包含 <h4> 标题。

import { fetchText } from './helpers.mjs';
import { load as cheerioLoad } from 'cheerio';

async function handler() {
    const html = await fetchText('https://www.canva.dev/blog/engineering/tag/infrastructure/');
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
        title: 'Canva Engineering - Infrastructure',
        link: 'https://www.canva.dev/blog/engineering/tag/infrastructure/',
        item: unique,
    };
}

export const route = {
    path: '/canva/infrastructure',
    categories: ['programming'],
    example: '/tac/canva/infrastructure',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Canva Engineering - Infrastructure',
    maintainers: ['tac'],
    handler,
};
