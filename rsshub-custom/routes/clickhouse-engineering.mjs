// ClickHouse Engineering 分类。
// 上游：clickhouse.com/blog?category=engineering（Next.js 列表页）。

import { parseListing } from './helpers.mjs';

export const route = {
    path: '/clickhouse/engineering',
    categories: ['programming'],
    example: '/tac/clickhouse/engineering',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'ClickHouse Engineering',
    maintainers: ['tac'],
    handler: async () =>
        parseListing('https://clickhouse.com/blog?category=engineering', {
            linkSelector: 'a[href*="/blog/"]',
            titleSelector: '',
            urlPatterns: ['/blog/'],
            siteTitle: 'ClickHouse Blog - Engineering',
        }),
};
