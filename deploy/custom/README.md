# h6k.top 生产部署模板

此目录为 Horizon-LK 定制镜像的生产配置。应用摘要固定为 `sha256:866c6a89500c667971d8314595101107e1467fe5e2e77e928419039d6b89dbca`；初始化脚本拉取 PostgreSQL 18 / Redis 8 官方镜像，并将仓库摘要固定到服务器 `.env`。升级应用时单独审查并修改应用摘要。

## 服务器目录与凭据

将本目录的公开配置与脚本复制到服务器 `/opt/sub2api`，由 root 管理；新建目录使用 `0700`。实际 `.env` 由 `initialize.py` 在服务器本地生成，root 持有、权限 `0600`；`.env.example` 仅说明变量，不用手工填密码。各密码、JWT 和 TOTP 密钥独立随机生成，使用 64 位十六进制值；管理员为 `admin@h6k.top`。不要把实际 `.env`、应用配置、数据库或备份复制进源码仓库，也不要把带展开凭据的 `docker compose config` 输出保存或发回聊天。

持久目录为 `/opt/sub2api/data`、`/opt/sub2api/postgres`、`/opt/sub2api/redis`。应用写入 `data/config.yaml` 和安装锁；固定 JWT/TOTP 密钥必须连同配置保存。PostgreSQL 挂载父目录 `/var/lib/postgresql`，使用 PG18 默认的版本化数据目录 `/var/lib/postgresql/18/docker`，避免挂错位置丢失数据。这与上游 Compose 显式设置 `PGDATA=/var/lib/postgresql/data` 的旧布局不同，不能直接混用旧数据目录；旧部署切换应先导出并在隔离环境恢复验证。本模板用于新实例空目录。目录首次为空才会初始化数据库或管理员，不可拿生产启动流程覆盖已有数据。

## 首次安装与初始化

以下命令在已核验的空白 Ubuntu 24.04 AMD64 服务器执行。`install-host.sh` 从 Docker 官方 APT 仓库安装 Docker Engine、Compose 插件及 Ubuntu 的 Nginx、Certbot，并启用 Docker/Nginx，不重启实例。先检查服务器路由，再运行初始化：

```bash
sudo bash /opt/sub2api/install-host.sh
sudo python3 /opt/sub2api/initialize.py
```

`initialize.py` 要求 root，拒绝已存在的 `.env` 或非空 `data`、`postgres`、`redis` 目录。它创建或复用独立桥网络 `sub2api-prod-backend`，取得 Docker 动态网关并以 `/32` 写入 `TRUSTED_PROXY_CIDR`；拉取并固定官方 PG/Redis 镜像摘要，生成独立固定凭据，最后独占创建 `.env`，不打印密码或密钥。它还从已固定的 PG 镜像查询 postgres 用户的实际 UID/GID，并设置主机 `postgres` 挂载父目录的所有权：PG18 切换运行用户后必须能穿过该目录，不能把它留成 root 所有的 `0700`。不要硬编码某个镜像版本的 UID。

这里的可信地址是主机 Nginx 进入容器时的桥网关，不能直接填 `127.0.0.1` 或信任所有私网。配置关闭上游旧版原始转发头信任开关，由明确的可信代理处理客户端 IP。若初始化在写 `.env` 前失败，先检查失败原因和镜像/目录状态再重试；生成成功后不要重跑或删除 `.env`。

## 容器与反向代理

```bash
sudo docker compose --env-file /opt/sub2api/.env -f /opt/sub2api/compose.yml config --quiet
sudo docker compose --env-file /opt/sub2api/.env -f /opt/sub2api/compose.yml up -d --wait --wait-timeout 600
```

应用仅发布到 `127.0.0.1:8080`；PostgreSQL、Redis 不发布主机端口。应用容器需要通过桥网络出网访问上游，不能将该网络设为 `internal: true`。日志每个服务最多保留三个 10 MiB 文件。依赖健康检查通过后应用才启动；启动会执行迁移。`/health` 只证明进程响应，不能代替数据库、管理员登录及真实请求验收。

## HTTPS 与续期

先将 `nginx-http.conf` 安装到主机 `/etc/nginx/sites-available/sub2api`，启用对应链接，创建 `/var/www/letsencrypt` 并保持 `0755`。先执行 `sudo nginx -t`，通过后重载。该初始站点只提供 ACME challenge，其他请求暂返回 503。DNS A 记录已指向实例、80 可达后，按证书机构的条款完成首次签发：

```bash
sudo certbot certonly --webroot -w /var/www/letsencrypt -d h6k.top
```

证书生成后用 `nginx-https.conf` 替换站点文件，再执行 `sudo nginx -t && sudo systemctl reload nginx`。TLS 站点把 HTTP 重定向至 HTTPS；ACME webroot 始终保留。启用发行版的 `certbot.timer`，创建 root 管理的 `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx`（可执行，内容为 `#!/bin/sh` 和 `nginx -t && systemctl reload nginx`），随后运行 `sudo certbot renew --dry-run` 验证续期。

Nginx 显式保留 WebSocket Upgrade，关闭代理响应缓冲、请求缓冲、缓存和 gzip，读写空闲超时 3600 秒，便于 SSE 与长生成请求。该超时是两次读写之间的等待期限，不表示已验证一小时的上游连接。

仅阻止 `POST /api/v1/admin/system/update`、`POST /api/v1/admin/system/rollback`（含尾斜杠），返回 403。版本检查和查看回滚版本的 GET 接口照常转发。域名直连的 Nginx 覆盖转发 IP 头，避免客户端伪造。主机本地或容器网络直接请求 8080 会绕过 Nginx，因此管理员不得在容器内运行官方原位更新。

拦截键使用 `$request_method:$uri`，因此查询字符串不参与匹配，百分号编码、点段按 Nginx 规范化 URI 处理；普通 `map` 字符串本身不区分大小写。相关规则见 [Nginx map](https://nginx.org/en/docs/http/ngx_http_map_module.html)、[URI 规范化](https://nginx.org/en/docs/http/ngx_http_core_module.html#location)。现场还应测试编码、重复斜杠、点段及大小写变体；模板只读核对不能代替实际代理验收。

## 上线验收与回滚

`verify-site.py` 仅接受本机应用地址或正式 HTTPS 地址，要求 root，从本机 `.env` 读取初始管理员密码，登录令牌只留在内存，不打印密码、令牌或 API 响应。它验证健康、安装锁、管理员身份与权限、首页及首个 JavaScript 资源。先验证应用，再在证书与代理就绪后验证域名：

```bash
sudo python3 /opt/sub2api/verify-site.py --url http://127.0.0.1:8080
sudo python3 /opt/sub2api/verify-site.py --url https://h6k.top --proxy
```

`--proxy` 还验证两个原位更新/回滚 POST 接口和尾斜杠返回 403，版本检查 GET 能到达应用认证层。重启持久性使用 `--record` 保存无凭据的管理员 ID、配置与环境文件摘要及安装锁状态，文件权限 `0600`、拒绝覆盖；重启后 `--compare` 核对同一基线：

```bash
sudo python3 /opt/sub2api/verify-site.py --url https://h6k.top --proxy --record /opt/sub2api/persistence-baseline.json
sudo docker compose --env-file /opt/sub2api/.env -f /opt/sub2api/compose.yml restart
sudo docker compose --env-file /opt/sub2api/.env -f /opt/sub2api/compose.yml up -d --wait --wait-timeout 600
sudo python3 /opt/sub2api/verify-site.py --url https://h6k.top --proxy --compare /opt/sub2api/persistence-baseline.json
```

如已保存过基线，复用 `--compare`，不要覆盖旧基线。管理员主动修改密码后，脚本保存的初始密码将不再可用；应调整验收方式，不要为通过检查重置生产密码。

- 检查 Compose 所有服务健康、`ss` 监听符合预期、HTTP 跳转、TLS 域名/有效期、页面加载，以及 `/setup/status` 的 `needs_setup=false`。
- 使用内存中的登录令牌检查 `/api/v1/auth/me` 为管理员，不保存令牌到日志。首次管理员尚未确认上游合规声明时，普通管理接口可能返回 `423 ADMIN_COMPLIANCE_ACK_REQUIRED`；这不代表登录失败，不能为验收自动代签声明。
- 验证两个 POST 原位写接口为 403、版本 GET 未被 Nginx 错误拦截；应用重建后确认配置、数据库记录及固定密钥保留。实际 SSE、备份恢复与容量由后续步骤单独验收。
- 升级前备份数据库、应用数据、配置和密钥并保存旧摘要。启动发生数据库迁移后，不能仅回退镜像；需恢复经过演练、与镜像匹配的数据。停止 Compose 会保留绑定目录；不要删除持久目录或使用数据库主版本替换来回滚。

模板本身不包含备份调度和异机备份凭据；这些在独立恢复验收步骤配置。模板验证不等于服务器已部署，实际执行者应在交付记录中写明镜像摘要、实际运行版本和已完成检查。
