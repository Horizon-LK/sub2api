# 二次开发与上游更新

## 仓库和首次基线

- 自有仓库：`https://github.com/Horizon-LK/sub2api`，生产源码分支为 `custom`。
- `origin` 指向自有 Fork，`upstream` 指向 `https://github.com/Wei-Shaw/sub2api.git`。
- 首次基线是官方 `v0.2.18`，提交 `ac1b8f1271be0d674fa6f074403c1410f30a3a81`。
- 保留上游许可证、版权和来源；不改 Go module 路径，不改现有业务接口。
- 本仓库是独立源码目录。PEM、AWS 登录缓存、账号文件、生产配置及数据不能放入仓库或构建上下文。

## 日常开发

从 `custom` 创建 `feature/功能名` 分支，小范围修改、独立提交，通过 CI 后再合并。
前端页面与后端功能都在本仓库修改，禁止在运行中的生产容器内直接改程序。

本地开发按 [dev/README.md](dev/README.md) 准备独立数据库与随机凭据。
前端 Vite 自动更新页面；后端 Air 监视文件变化、重新编译并自动重启。
开发进程和数据不连接生产环境；生产仅通过明确版本的镜像发布。

## 构建自己的镜像

1. 将已审查的提交推送到 `custom`，等待该提交的 **CI** 成功。CI 执行后端单元/容器集成测试、lint、前端检查及关键测试等。
2. 打开 Actions 的 **Custom image**，选择 `custom`，填写版本号，例如 `0.2.18-custom.1`。
3. 工作流再次核对该精确提交的 CI 成功记录，然后用根 `Dockerfile` 构建 `linux/amd64` 镜像。不会部署到服务器。
4. 镜像标签为 `版本号-提交前12位`，只发这个版本标签，不发 `latest`，已存在的标签拒绝覆盖。
5. 工作流验证应用版本及 PostgreSQL 备份客户端，输出 `image-reference` 产物。生产必须使用其中的 `ghcr.io/horizon-lk/sub2api@sha256:...` 摘要。

构建显式传入 VERSION、COMMIT、DATE。上游该标签内的 `backend/cmd/server/VERSION` 仍是 `0.2.17`，因此不能依赖容器自动推断版本。
使用 **Custom image** 发布自有镜像；原上游 **Release** 会执行其他发布行为，不用于此流程。

GHCR 首次发布默认私有；公开 Fork 不代表镜像已经公开。发布后须核对可见性。
若选择公开镜像，在 GitHub Packages 的 package settings 中完成公开操作后，验收匿名拉取。
镜像公开后无法改回私有，公开前必须确认只包含本仓库代码和公开依赖。
生产不保存个人 GitHub 令牌。

## 合并官方更新

```bash
git switch custom
git pull --ff-only origin custom
git fetch upstream --tags
git switch -c upgrade/vX.Y.Z
git merge --no-ff vX.Y.Z
```

解决冲突后，检查业务修改、数据库迁移和镜像依赖，运行 CI，在独立数据库恢复副本上演练迁移，再合并到 `custom` 并发布新的 custom 版本。
不要修改、改名或删除已经执行过的 SQL 迁移；新增变更用新的迁移文件。
更新应用与更新 PostgreSQL/Redis 主版本分开处理。

升级前备份数据库、应用数据、配置及固定密钥；保留上一镜像摘要。
应用启动会执行数据库迁移，因此回退镜像不等于回退数据库。迁移发生后，按演练结果恢复匹配的数据与镜像。
后台官方二进制原位更新及回滚入口由生产反向代理阻止，版本检查保留；该配置在站点部署步骤完成。

## 验证边界

CI 与镜像构建成功不代表生产站点、证书、真实上游 API、备份恢复或并发容量已经验收。
本地开发脚本的实际热更新验收情况见 `dev/README.md`。
