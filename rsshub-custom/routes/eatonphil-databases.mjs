// Phil Eaton（databases / distsys 方向）。
// 上游：notes.eatonphil.com/tags/databases.html（静态 tag 列表页）。

import { parseListing } from './helpers.mjs';

export const route = {
    path: '/eatonphil/databases',
    categories: ['programming'],
    example: '/tac/eatonphil/databases',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Phil Eaton - databases',
    maintainers: ['tac'],
    handler: async () =>
        parseListing('https://notes.eatonphil.com/tags/databases.html', {
            linkSelector: 'a[href*=".html"]',
            urlPatterns: ['notes.eatonphil.com'],
            siteTitle: 'Phil Eaton - databases',
        }),
};
