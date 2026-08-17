// Modal Engineering（GPU runtime / serverless 基础设施）。
// 上游：modal.com/blog/atom.xml。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/modal/blog',
    categories: ['programming'],
    example: '/tac/modal/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Modal Engineering',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://modal.com/blog/atom.xml', {
            title: 'Modal Blog',
            siteUrl: 'https://modal.com/blog',
        }),
};
