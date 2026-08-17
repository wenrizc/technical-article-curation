// ScyllaDB Engineering 分类。
// 上游：www.scylladb.com/category/engineering/feed/（WordPress 分类 feed）。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/scylladb/engineering',
    categories: ['programming'],
    example: '/tac/scylladb/engineering',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'ScyllaDB Engineering',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://www.scylladb.com/category/engineering/feed/', {
            title: 'ScyllaDB Engineering',
            siteUrl: 'https://www.scylladb.com/blog/engineering/',
        }),
};
