// Figma Infrastructure 栏目。
// 上游：www.figma.com/blog/infrastructure/（无 RSS）。
// 标题在 article[aria-label] 上，链接在其内部 <a>，需专用解析。

import { fetchText } from './helpers.mjs';
import { load as cheerioLoad } from 'cheerio';

export const route = {
    path: '/figma/infrastructure',
    categories: ['programming'],
    example: '/tac/figma/infrastructure',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Figma Infrastructure',
    maintainers: ['tac'],
    handler: async () => {
        const html = await fetchText('https://www.figma.com/blog/infrastructure/');
        const $ = cheerioLoad(html);
        const items = [];
        $('article').each((_, el) => {
            const node = $(el);
            const label = node.attr('aria-label');
            const link = node.find('a[href*="/blog/"]').first().attr('href');
            if (!link || !label) {
                return;
            }
            items.push({ title: label.trim(), link: new URL(link, 'https://www.figma.com').href });
        });
        return {
            title: 'Figma Blog - Infrastructure',
            link: 'https://www.figma.com/blog/infrastructure/',
            item: items,
        };
    },
};
