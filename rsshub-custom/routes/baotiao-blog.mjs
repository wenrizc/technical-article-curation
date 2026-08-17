// 做有积累的事情（baotiao）—— 数据库内核个人博客。
// 上游：baotiao.github.io（Jekyll），有 feed.xml。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/baotiao/blog',
    categories: ['programming'],
    example: '/tac/baotiao/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: '做有积累的事情 (baotiao)',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://baotiao.github.io/feed.xml', {
            title: '做有积累的事情 (baotiao)',
            siteUrl: 'https://baotiao.github.io/',
        }),
};
