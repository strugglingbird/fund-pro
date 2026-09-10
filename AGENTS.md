# Project Maintenance Rules

## Baseline standards

- Authoritative coding & architecture standards live in [`docs/CODE_STANDARDS.md`](docs/CODE_STANDARDS.md). Any structural decision (new module, new component, naming, cache strategy, SQL change) must follow it. When this file changes, reviewers check the standards doc is consistent.

## README synchronization

- Every code change must review README.md and update affected or newly introduced behavior in the same change/commit. Documentation is part of completion.
- Cover features, layout, architecture, APIs, dependencies, environment variables, database schema/migrations, data flows, providers, calculations, caches, scheduled jobs, build/deployment and verification as applicable.
- Remove obsolete descriptions. Describe actual implementation and limitations; do not claim planned features or checks not performed.
- If documented behavior is unaffected, state that README was reviewed and no update was needed in the completion report. Avoid meaningless edits.
- README is Chinese. Use placeholders instead of credentials, personal holdings, databases, backups or signing material.

## Product conventions

- Async views need Skeleton loading, success, empty and error states; preserve valid data after refresh failure where appropriate.
- Keep OTC official NAV separate from estimates and verify China Standard Time dates. Document fallback limitations.
- Database changes must support SQLite and MySQL. Do not silently discard archives.
- Deploy complete frontend assets, verify script/stylesheet content types and relevant business APIs. HTTP 200 alone is not sufficient verification.
- Preserve user changes and keep secrets and generated artifacts out of commits.

## Security / network exposure

- `MYSQL_BIND_ADDRESS` 默认 `0.0.0.0`（监听公网）。3306 暴露到公网后必须依赖云安全组 / OS 防火墙做白名单。
- 修改默认 `0.0.0.0` → `127.0.0.1` 只能减小攻击面，**不能** 替代传输加密；远程访问仍需走 SSH 隧道或 Caddy 反代。
- 永远不要在 `.env.deploy` 里提交真实密码，使用 `.env.deploy.example` 占位符。
- `quant-api` 容器只通过 Compose 网络访问 `db:3306`，不直接走公网；不要把 `quant-api` 端口 5000 暴露到公网。
- Caddy 仅暴露 80/443；新增端口必须同时更新 README 与 docker-compose 注释。
