// Stripe Engineering 栏目。
// 上游：stripe.dev/blog/topic/engineering（全站博客的工程子栏目，无 RSS）。

import { parseListing } from './helpers.mjs';

export const route = {
    path: '/stripe/engineering',
    categories: ['programming'],
    example: '/tac/stripe/engineering',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Stripe Engineering',
    maintainers: ['tac'],
    handler: async () =>
        parseListing('https://stripe.dev/blog/topic/engineering', {
            linkSelector: 'a[href*="/blog/"]',
            titleSelector: '.text-md, h2, h3',
            urlPatterns: ['/blog/'],
            siteTitle: 'Stripe Engineering',
        }),
};
