// Redpanda Engineering。
// 上游：www.redpanda.com/blog/rss.xml（全站 feed，含产品/营销内容，二次过滤交给评估阶段）。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/redpanda/blog',
    categories: ['programming'],
    example: '/tac/redpanda/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Redpanda Blog',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://www.redpanda.com/blog/rss.xml', {
            title: 'Redpanda Blog',
            siteUrl: 'https://www.redpanda.com/blog',
        }),
};
