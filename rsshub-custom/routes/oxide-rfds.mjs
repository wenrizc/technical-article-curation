// Oxide Public RFDs（公开请求讨论稿）。
// 上游：rfd.shared.oxide.computer/（无 RSS）。
// 页面为 Next.js RSC flight 数据，内嵌 RFD 列表：
// 形如 \"NNNN\",\"标题\",\"https://github.com/oxidecomputer/rfd/tree/.../rfd/NNNN\",...

import { fetchText } from './helpers.mjs';

async function handler() {
    const html = await fetchText('https://rfd.shared.oxide.computer/');
    const re = /\\"(\d{4})\\",\\"([^"\\]{3,120})\\",\\"(https:\/\/github\.com\/oxidecomputer\/rfd\/tree\/[^"\\]+)\\/g;
    const items = [];
    const seen = new Set();
    for (const m of html.matchAll(re)) {
        const number = m[1];
        const title = m[2];
        const link = m[3];
        if (seen.has(link)) {
            continue;
        }
        seen.add(link);
        items.push({ title: `RFD ${number}: ${title}`, link });
    }
    return {
        title: 'Oxide Public RFDs',
        link: 'https://rfd.shared.oxide.computer/',
        item: items,
    };
}

export const route = {
    path: '/oxide/rfds',
    categories: ['programming'],
    example: '/tac/oxide/rfds',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'Oxide Public RFDs',
    maintainers: ['tac'],
    handler,
};
