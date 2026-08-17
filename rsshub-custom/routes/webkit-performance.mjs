// WebKit Performance 分类。
// 上游：webkit.org/blog/category/performance/feed/（分类 RSS）。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/webkit/performance',
    categories: ['programming'],
    example: '/tac/webkit/performance',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'WebKit Performance',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://webkit.org/blog/category/performance/feed/', {
            title: 'WebKit Performance',
            siteUrl: 'https://webkit.org/blog/category/performance/',
        }),
};
