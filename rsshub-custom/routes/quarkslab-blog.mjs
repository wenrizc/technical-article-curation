// Quarkslab Blog（逆向 / 内核 / 硬件安全）。
// 上游：blog.quarkslab.com/feeds/all.rss.xml。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/quarkslab/blog',
    categories: ['security'],
    example: '/tac/quarkslab/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Quarkslab Blog',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://blog.quarkslab.com/feeds/all.rss.xml', {
            title: 'Quarkslab Blog',
            siteUrl: 'https://blog.quarkslab.com/',
        }),
};
