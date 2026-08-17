// The Consensus - Articles（排除 Weekly / Jobs / Funding）。
// 上游：theconsensus.dev/rss.xml 混合 Articles 与 Weekly 新闻简报。

import { fetchText, parseFeed } from './helpers.mjs';

export const route = {
    path: '/theconsensus/articles',
    categories: ['programming'],
    example: '/tac/theconsensus/articles',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'The Consensus - Articles',
    maintainers: ['tac'],
    handler: async () => {
        const xml = await fetchText('https://theconsensus.dev/rss.xml');
        const items = parseFeed(xml, 'https://theconsensus.dev/rss.xml');
        const filtered = items.filter((it) => !/weekly/i.test(it.title));
        return {
            title: 'The Consensus - Articles',
            link: 'https://theconsensus.dev/',
            item: filtered,
        };
    },
};
