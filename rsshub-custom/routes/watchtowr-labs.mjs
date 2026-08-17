// watchTowr Labs（CVE 根因 / pre-auth 漏洞研究）。
// 上游：labs.watchtowr.com/feed/。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/watchtowr/labs',
    categories: ['security'],
    example: '/tac/watchtowr/labs',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'watchTowr Labs',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://labs.watchtowr.com/feed/', {
            title: 'watchTowr Labs',
            siteUrl: 'https://labs.watchtowr.com/',
        }),
};
