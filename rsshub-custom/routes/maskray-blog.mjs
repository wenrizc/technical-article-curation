// MaskRay（编译器 / 链接器 / ELF / LLVM）。
// 宿主机直连 maskray.me 超时，改由容器内 curl 经 mihomo 代理抓上游 Atom。

import { proxyFeed } from './helpers.mjs';

export const route = {
    path: '/maskray/blog',
    categories: ['programming'],
    example: '/tac-custom/maskray/blog',
    parameters: {},
    features: {
        requireConfig: false,
        requirePuppeteer: false,
        antiCrawler: false,
        supportBT: false,
        supportPodcast: false,
        supportScihub: false,
    },
    name: 'MaskRay',
    maintainers: ['tac'],
    handler: async () =>
        proxyFeed('https://maskray.me/blog/atom.xml', {
            title: 'MaskRay',
            siteUrl: 'https://maskray.me/blog/',
        }),
};
