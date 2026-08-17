// LinkedIn Engineering - Scalability。
// 上游：www.linkedin.com/blog/engineering/scalability（无 RSS 列表页）。

import { parseListing } from './helpers.mjs';

export const route = {
    path: '/linkedin/scalability',
    categories: ['programming'],
    example: '/tac/linkedin/scalability',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'LinkedIn Engineering - Scalability',
    maintainers: ['tac'],
    handler: async () =>
        parseListing('https://www.linkedin.com/blog/engineering/scalability', {
            linkSelector: 'a.grid-post__link',
            titleSelector: '',
            urlPatterns: ['/blog/engineering/'],
            siteTitle: 'LinkedIn Engineering - Scalability',
        }),
};
