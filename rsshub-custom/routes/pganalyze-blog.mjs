// pganalyze Blog（Postgres Internals / Query Performance 方向）。
// 上游：pganalyze.com/feed.xml（全站 feed，主题以 Postgres 性能与内核为主）。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/pganalyze/blog',
    categories: ['programming'],
    example: '/tac/pganalyze/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'pganalyze Blog',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://pganalyze.com/feed.xml', {
            title: 'pganalyze Blog',
            siteUrl: 'https://pganalyze.com/blog',
        }),
};
