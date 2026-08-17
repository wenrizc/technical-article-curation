// Phil Eaton（distsys 方向）。
// 上游：notes.eatonphil.com/tags/distsys.html（静态 tag 列表页）。

import { parseListing } from './helpers.mjs';

export const route = {
    path: '/eatonphil/distsys',
    categories: ['programming'],
    example: '/tac/eatonphil/distsys',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Phil Eaton - distsys',
    maintainers: ['tac'],
    handler: async () =>
        parseListing('https://notes.eatonphil.com/tags/distsys.html', {
            linkSelector: 'a[href*=".html"]',
            urlPatterns: ['notes.eatonphil.com'],
            siteTitle: 'Phil Eaton - distsys',
        }),
};
