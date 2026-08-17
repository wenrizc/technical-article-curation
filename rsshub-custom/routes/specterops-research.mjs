// SpecterOps - Research & Tradecraft 分类。
// 上游：specterops.io/blog/category/research/feed/（WordPress 分类 feed）。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/specterops/research',
    categories: ['security'],
    example: '/tac/specterops/research',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'SpecterOps Research & Tradecraft',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://specterops.io/blog/category/research/feed/', {
            title: 'SpecterOps Research & Tradecraft',
            siteUrl: 'https://specterops.io/blog/category/research/',
        }),
};
