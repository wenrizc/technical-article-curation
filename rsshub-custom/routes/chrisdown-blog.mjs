// Chris Down（Linux / cgroup / kernel / SRE）。
// 上游：chrisdown.name/feed.xml。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/chrisdown/blog',
    categories: ['programming'],
    example: '/tac/chrisdown/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Chris Down',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://chrisdown.name/feed.xml', {
            title: 'Chris Down',
            siteUrl: 'https://chrisdown.name/',
        }),
};
