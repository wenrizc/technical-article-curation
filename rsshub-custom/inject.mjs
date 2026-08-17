// 将自定义路由注入到 RSSHub dist：
// 1. 复制 routes/*.mjs 到 dist/（helpers 复制为 tac-helpers.mjs，路由模块引用同步改写）
// 2. 在 dist/routes-*.mjs 注册表中追加 namespace "tac-custom"（文本拼接，幂等）
// 该脚本应在 RSSHub 容器内、每次启动前执行。

import { cpSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const distDir = '/app/dist';
const routesDir = '/app/tac-custom-routes';
const namespace = 'tac-custom';
const helpersModule = 'tac-helpers.mjs';

// 1. 复制 helpers 与路由模块，改写 helpers 引用
cpSync(join(routesDir, 'helpers.mjs'), join(distDir, helpersModule));
console.log(`[tac-custom] copied ${helpersModule}`);

const customFiles = readdirSync(routesDir).filter((f) => f.endsWith('.mjs') && f !== 'helpers.mjs');
const routeDefs = [];
for (const file of customFiles) {
    const moduleFile = `tac-${file}`;
    let src = readFileSync(join(routesDir, file), 'utf8');
    src = src.replaceAll("from './helpers.mjs'", `from './${helpersModule}'`);
    writeFileSync(join(distDir, moduleFile), src);
    // 读取 path 定义用于注册表
    const m = src.match(/path:\s*'([^']+)'/);
    const nameM = src.match(/name:\s*'([^']+)'/);
    if (!m || !nameM) {
        throw new Error(`[tac-custom] ${file}: route path or name is missing`);
    }
    if (routeDefs.some((route) => route.path === m[1])) {
        throw new Error(`[tac-custom] ${file}: duplicate route path ${m[1]}`);
    }
    routeDefs.push({ path: m[1], name: nameM[1], moduleFile });
    console.log(`[tac-custom] copied ${moduleFile}`);
}

// 2. 生成注册表 namespace 文本
const esc = (s) => s.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
const routeEntries = routeDefs
    .map(
        (r) =>
            `"${r.path}":{path:\`${esc(r.path)}\`,name:\`${esc(r.name)}\`,url:\`tac.local\`,maintainers:[\`tac\`],example:\`${esc(r.path)}\`,categories:[\`programming\`],features:{requireConfig:!1,requirePuppeteer:!1,antiCrawler:!1,supportBT:!1,supportPodcast:!1,supportScihub:!1},location:\`${esc(r.moduleFile)}\`,module:()=>import(\`./${esc(r.moduleFile)}\`)}`
    )
    .join(',');
const nsText = `"${namespace}":{routes:{${routeEntries}},apiRoutes:{},name:\`TAC Custom\`,url:\`tac.local\`,categories:[\`programming\`],description:\`\`,lang:\`zh-CN\`}`;

// 3. 注入每个注册表文件：已存在 tac-custom 时整体替换（保证新增路由生效），否则插入。
let injected = 0;
const registryFiles = readdirSync(distDir).filter((f) => /^routes-[A-Za-z0-9_-]+\.mjs$/.test(f));
for (const file of registryFiles) {
    const fp = join(distDir, file);
    let content = readFileSync(fp, 'utf8');
    const startMarker = `"${namespace}":{`;
    const startIdx = content.indexOf(startMarker);
    const registryPattern = /^var e=\{(.*)\};export\{e as default\};$/s;
    if (startIdx < 0 && !registryPattern.test(content)) {
        continue;
    }
    if (startIdx >= 0) {
        // 用明确的结束锚点定位 namespace 块：以 `lang:\`zh-CN\`}` 结尾
        const endMarker = 'lang:`zh-CN`}';
        const endIdx = content.indexOf(endMarker, startIdx);
        if (endIdx < 0) {
            console.error(`[tac-custom] ${file}: cannot find namespace end marker`);
            continue;
        }
        const blockEnd = endIdx + endMarker.length;
        content = content.slice(0, startIdx) + nsText + content.slice(blockEnd);
        writeFileSync(fp, content);
        console.log(`[tac-custom] ${file} namespace refreshed (${routeDefs.length} routes)`);
        injected++;
        continue;
    }
    const m = content.match(registryPattern);
    if (!m) {
        console.error(`[tac-custom] unexpected registry format: ${file}`);
        continue;
    }
    writeFileSync(fp, `var e={${nsText},${m[1]}};export{e as default};`);
    injected++;
    console.log(`[tac-custom] injected into ${file}`);
}
if (injected === 0) {
    throw new Error('[tac-custom] no compatible RSSHub route registry found');
}
console.log(`[tac-custom] done: ${routeDefs.length} routes, ${injected} registries updated`);
