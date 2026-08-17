// Airbnb Engineering - Infrastructure 分类。
// 上游：medium.com/feed/airbnb-engineering/tagged/infrastructure（Medium feed，需代理）。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/airbnb/infrastructure',
    categories: ['programming'],
    example: '/tac-custom/airbnb/infrastructure',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Airbnb Engineering - Infrastructure',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://medium.com/feed/airbnb-engineering/tagged/infrastructure', {
            title: 'Airbnb Engineering - Infrastructure',
            siteUrl: 'https://medium.com/airbnb-engineering',
            timeoutSeconds: 60,
        }),
};
