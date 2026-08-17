// vLLM Blog（inference engineering / performance）。
// 上游：vllm.ai/blog/rss.xml。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/vllm/blog',
    categories: ['programming'],
    example: '/tac/vllm/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'vLLM Blog',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://vllm.ai/blog/rss.xml', {
            title: 'vLLM Blog',
            siteUrl: 'https://vllm.ai/blog',
        }),
};
