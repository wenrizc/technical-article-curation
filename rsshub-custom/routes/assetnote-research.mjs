// Assetnote Research（Web/云 RCE、SSRF、auth bypass 研究）。
// 上游：blog.assetnote.io/feed.xml。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/assetnote/research',
    categories: ['security'],
    example: '/tac/assetnote/research',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Assetnote Research',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://blog.assetnote.io/feed.xml', {
            title: 'Assetnote Research',
            siteUrl: 'https://blog.assetnote.io/',
        }),
};
