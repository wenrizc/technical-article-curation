// Apache DataFusion Blog。
// 上游：datafusion.apache.org/blog/feed.xml。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/datafusion/blog',
    categories: ['programming'],
    example: '/tac/datafusion/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Apache DataFusion Blog',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://datafusion.apache.org/blog/feed.xml', {
            title: 'Apache DataFusion Blog',
            siteUrl: 'https://datafusion.apache.org/blog/',
        }),
};
