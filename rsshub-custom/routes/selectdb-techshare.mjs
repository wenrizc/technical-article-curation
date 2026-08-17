// SelectDB 技术分享（categoryId=2）博客。
// 上游：www.selectdb.com/blogs?categoryId=2，文章卡片为 a.blog-card。

import { parseListing } from './helpers.mjs';

export const route = {
    path: '/selectdb/techshare',
    categories: ['programming'],
    example: '/tac/selectdb/techshare',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'SelectDB 技术分享',
    maintainers: ['tac'],
    handler: async () =>
        parseListing('https://www.selectdb.com/blogs?categoryId=2', {
            linkSelector: 'a.blog-card',
            urlPatterns: ['/blog/'],
            siteTitle: 'SelectDB 技术分享',
        }),
};
