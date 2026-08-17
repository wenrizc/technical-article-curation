// DuckDB Engineering Blog（news 栏目，含 Deep Dive / Benchmarks / Extensions）。
// 上游：duckdb.org/news/。文章卡片 .postpreview，标题在 <a title> 上。

import { fetchText } from './helpers.mjs';
import { load as cheerioLoad } from 'cheerio';

export const route = {
    path: '/duckdb/blog',
    categories: ['programming'],
    example: '/tac/duckdb/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'DuckDB Engineering Blog',
    maintainers: ['tac'],
    handler: async () => {
        const html = await fetchText('https://duckdb.org/news/');
        const $ = cheerioLoad(html);
        const items = [];
        $('a.blocklink').each((_, el) => {
            const node = $(el);
            const href = node.attr('href');
            const title = node.attr('title') || node.find('h3').first().text().trim();
            if (!href || !title) {
                return;
            }
            items.push({ title: title.trim(), link: new URL(href, 'https://duckdb.org').href });
        });
        return {
            title: 'DuckDB Engineering Blog',
            link: 'https://duckdb.org/news/',
            item: items,
        };
    },
};
