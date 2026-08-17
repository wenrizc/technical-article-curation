// LinkedIn Engineering - Architecture。
// 上游：www.linkedin.com/blog/engineering/architecture（无 RSS 列表页）。

import { parseListing } from './helpers.mjs';

export const route = {
    path: '/linkedin/architecture',
    categories: ['programming'],
    example: '/tac/linkedin/architecture',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'LinkedIn Engineering - Architecture',
    maintainers: ['tac'],
    handler: async () =>
        parseListing('https://www.linkedin.com/blog/engineering/architecture', {
            linkSelector: 'a.grid-post__link',
            titleSelector: '',
            urlPatterns: ['/blog/engineering/'],
            siteTitle: 'LinkedIn Engineering - Architecture',
        }),
};
