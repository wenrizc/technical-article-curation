// JuiceFS 工程技术（Engineering）分类列表页。
// 上游：juicefs.com/en/blog/engineering/（无 RSS，静态列表页）。

import { parseListing } from './helpers.mjs';

export const route = {
    path: '/juicefs/engineering',
    categories: ['programming'],
    example: '/tac/juicefs/engineering',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'JuiceFS 工程技术',
    maintainers: ['tac'],
    handler: async () =>
        parseListing('https://juicefs.com/en/blog/engineering/', {
            linkSelector: 'a[href*="/en/blog/engineering/"]',
            titleSelector: 'h2, h3, h4, span',
            urlPatterns: ['/en/blog/engineering/'],
            siteTitle: 'JuiceFS Engineering Blog',
        }),
};
