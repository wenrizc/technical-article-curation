// Oxide Public RFDs（公开请求讨论稿）。
// 上游：rfd.shared.oxide.computer/（无 RSS）。
// 页面为 Next.js RSC flight 数据，内嵌 RFD 列表：
// 形如 \"NNNN\",\"标题\",\"https://github.com/oxidecomputer/rfd/tree/<sha>/rfd/NNNN\",...
//
// 注意：上游链接带 commit SHA，SHA 变化会导致同一 RFD 被反复当作新条目（历史重复 900+ 条）。
// 因此对外统一输出稳定的渲染页地址 https://rfd.shared.oxide.computer/rfd/NNNN，并按编号去重。

import { fetchText } from './helpers.mjs';

// 与具体技术无关的元讨论稿，不作为文章源收录。
const EXCLUDED_TITLE_PATTERNS = [
    /Hiring Process/i,
    /Mission, Principles and Values/i,
    /Partnership as Shared Values/i,
    /Journal Club/i,
];

async function handler() {
    const html = await fetchText('https://rfd.shared.oxide.computer/');
    const re = /\\"(\d{4})\\",\\"([^"\\]{3,120})\\",\\"(https:\/\/github\.com\/oxidecomputer\/rfd\/tree\/[^"\\]+)/g;
    const items = [];
    const seen = new Set();
    for (const m of html.matchAll(re)) {
        const number = m[1];
        const title = m[2];
        if (seen.has(number)) {
            continue;
        }
        if (EXCLUDED_TITLE_PATTERNS.some((pattern) => pattern.test(title))) {
            continue;
        }
        seen.add(number);
        items.push({
            title: `RFD ${number}: ${title}`,
            link: `https://rfd.shared.oxide.computer/rfd/${number}`,
        });
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
