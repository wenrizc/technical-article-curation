// Pinterest Engineering - Infrastructure 分类。
// 上游：medium.com/feed/pinterest-engineering/tagged/infrastructure（Medium feed，需代理）。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/pinterest/infrastructure',
    categories: ['programming'],
    example: '/tac-custom/pinterest/infrastructure',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Pinterest Engineering - Infrastructure',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://medium.com/feed/pinterest-engineering/tagged/infrastructure', {
            title: 'Pinterest Engineering - Infrastructure',
            siteUrl: 'https://medium.com/pinterest-engineering',
            timeoutSeconds: 60,
        }),
};
