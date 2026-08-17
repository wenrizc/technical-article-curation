// QuestDB Engineering 分类。
// 上游：questdb.com/blog/?tag=engineering（无 RSS）。
// 文章卡片链接为绝对定位 <a>，标题在 aria-label 上。

import { fetchText } from './helpers.mjs';
import { load as cheerioLoad } from 'cheerio';

export const route = {
    path: '/questdb/engineering',
    categories: ['programming'],
    example: '/tac/questdb/engineering',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'QuestDB Engineering',
    maintainers: ['tac'],
    handler: async () => {
        const html = await fetchText('https://questdb.com/blog/?tag=engineering');
        const $ = cheerioLoad(html);
        const items = [];
        $('a[href*="/blog/"]').each((_, el) => {
            const node = $(el);
            const href = node.attr('href');
            const label = node.attr('aria-label');
            const sr = node.find('.sr-only').first().text().trim();
            const title = label || sr;
            if (!href || !title || href === '/blog/' || href.startsWith('/blog/?')) {
                return;
            }
            items.push({ title, link: new URL(href, 'https://questdb.com').href });
        });
        const seen = new Set();
        const unique = items.filter((it) => (seen.has(it.link) ? false : seen.add(it.link)));
        return {
            title: 'QuestDB Blog - Engineering',
            link: 'https://questdb.com/blog/?tag=engineering',
            item: unique,
        };
    },
};
