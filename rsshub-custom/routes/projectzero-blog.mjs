// Google Project Zero（0-day / 漏洞研究）。
// 上游：projectzero.google/feed.xml（Atom，需代理）。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/projectzero/blog',
    categories: ['security'],
    example: '/tac-custom/projectzero/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Google Project Zero',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://projectzero.google/feed.xml', {
            title: 'Google Project Zero',
            siteUrl: 'https://googleprojectzero.blogspot.com/',
            timeoutSeconds: 90,
        }),
};
