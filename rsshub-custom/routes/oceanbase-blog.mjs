// OceanBase 社区博客 - Engineering 方向。
// 官方站点（www.oceanbase.com/blog/engineering）为 JS 渲染无 RSS；
// 社区博客 API（openwebapi.oceanbase.com）返回结构化文章列表，可按 engineering 分类过滤。

import { fetchText } from './helpers.mjs';

const API = 'https://openwebapi.oceanbase.com/api/web/blog/querySeoBlogPageList';

async function fetchPage(pageNo) {
    const body = JSON.stringify({ tagCode: 'engineering', currentPage: pageNo, pageNo, pageSize: 20, sortField: 'updateTime' });
    const text = await fetchText(API, {
        timeoutSeconds: 30,
        headers: { 'Content-Type': 'application/json' },
        method: 'POST',
        body,
    });
    return JSON.parse(text);
}

export const route = {
    path: '/oceanbase/blog',
    categories: ['programming'],
    example: '/tac/oceanbase/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'OceanBase 社区博客',
    maintainers: ['tac'],
    handler: async () => {
        const data = await fetchPage(1);
        const list = data?.data?.list || [];
        return {
            title: 'OceanBase 社区博客 - Engineering',
            link: 'https://www.oceanbase.com/blog/engineering',
            item: list
                .filter((it) => it && it.title)
                .map((it) => ({
                    title: it.title,
                    link: `https://open.oceanbase.com/blog/${it.oid}`,
                    pubDate: it.updateTime ? new Date(it.updateTime) : undefined,
                    description: it.summary || undefined,
                })),
        };
    },
};
