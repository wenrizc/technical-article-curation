// Greptime 技术（Engineering 分类）博客。
// 上游：greptime.com/blogs?category=engineering（Vue SPA，文章 URL 含日期 slug）。

import { parseListing } from './helpers.mjs';

export const route = {
    path: '/greptime/engineering',
    categories: ['programming'],
    example: '/tac/greptime/engineering',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Greptime 技术',
    maintainers: ['tac'],
    handler: async () =>
        parseListing('https://greptime.com/blogs?category=engineering', {
            linkSelector: 'a[href*="/blogs/"]',
            titleSelector: 'h2.article-title, h3.blog-card-title',
            // 只收工程/实践类文章，跳过 Product 发布与 Monthly 月报。
            excludeSelector: '.type',
            excludeValues: ['Product', 'Monthly'],
            urlPatterns: ['/blogs/20'],
            siteTitle: 'Greptime Blog - Engineering',
        }),
};
