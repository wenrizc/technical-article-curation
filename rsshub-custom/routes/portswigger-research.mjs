// PortSwigger Research（Web 安全研究文章）。
// 上游：portswigger.net/research/rss。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/portswigger/research',
    categories: ['security'],
    example: '/tac/portswigger/research',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'PortSwigger Research',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://portswigger.net/research/rss', {
            title: 'PortSwigger Research',
            siteUrl: 'https://portswigger.net/research',
        }),
};
