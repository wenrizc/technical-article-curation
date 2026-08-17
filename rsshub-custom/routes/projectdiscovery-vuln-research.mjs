// ProjectDiscovery - Vulnerability Research 分类。
// 上游：projectdiscovery.io/blog/category/vulnerability-research/1（无 RSS 列表页）。

import { parseListing } from './helpers.mjs';

export const route = {
    path: '/projectdiscovery/vulnerability-research',
    categories: ['security'],
    example: '/tac/projectdiscovery/vulnerability-research',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'ProjectDiscovery - Vulnerability Research',
    maintainers: ['tac'],
    handler: async () =>
        parseListing('https://projectdiscovery.io/blog/category/vulnerability-research/1', {
            linkSelector: 'a[href*="/blog/"]',
            titleSelector: '',
            urlPatterns: ['/blog/'],
            siteTitle: 'ProjectDiscovery Blog - Vulnerability Research',
        }),
};
