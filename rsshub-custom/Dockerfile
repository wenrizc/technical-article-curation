# 扩展 RSSHub 自定义路由镜像
# 基于官方 chromium-bundled 镜像，注入 TAC 自定义路由（tac-custom namespace）。
# 启动时执行 inject.mjs 将路由注入 dist（幂等），再运行官方入口。
# 官方入口为 `npm start`（node dist/index.mjs），此处直接调用 node。

FROM diygod/rsshub:chromium-bundled@sha256:e3d4018f7c68fab624c1da24cf429874f380addc81322342bb8c954ddb7eac21

COPY inject.mjs /app/tac-custom-inject.mjs
COPY routes/ /app/tac-custom-routes/

# 调整启动入口：先注入再启动。官方镜像 entrypoint 为 dumb-init，command 为 npm start。
CMD ["sh", "-c", "node /app/tac-custom-inject.mjs && npm start"]
