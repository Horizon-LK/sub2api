# 本地二次开发

本目录提供前端 Vite 热更新、后端 Air 自动重新编译并重启，以及独立的 PostgreSQL 18 / Redis 8。生产仍由发布镜像运行，不使用这些脚本。

## 前提

- Go **1.27.3**，与 `backend/go.mod` 一致。
- Node.js **24**、pnpm **9**，与项目镜像构建一致。
- Docker Desktop（Linux 容器）和 Docker Compose 插件，供本机开发数据库使用。
- Windows PowerShell 5.1 或 PowerShell 7；以下命令在源码仓库根目录执行。脚本不会安装系统软件。
- Air 固定为官方 [air-verse/air v1.67.4](https://github.com/air-verse/air/releases/tag/v1.67.4)，通过 `go run ...@v1.67.4` 运行，不改项目 `go.mod`。其 [官方配置](https://github.com/air-verse/air/blob/v1.67.4/air_example.toml) 支持 Windows 执行文件覆盖项。

## 第一次准备

```powershell
powershell -NoProfile -File dev/Initialize.ps1
docker compose --env-file dev/.env.local -f dev/compose.yml up -d --wait
pnpm --dir frontend install --frozen-lockfile
```

初始化会生成独立随机开发凭据，只写入已忽略的 `dev/.env.local`，不打印内容；文件已存在时拒绝覆盖。不要复制服务器 `.env`、配置、数据库、正式上游令牌或用户数据到这里。开发数据库与 Redis 只绑定本机 `127.0.0.1:15432` / `127.0.0.1:16379`，使用独立 Compose 项目及命名卷。

## 日常启动

打开两个 PowerShell 窗口，各执行一条：

```powershell
powershell -NoProfile -File dev/Start-Backend.ps1
```

```powershell
powershell -NoProfile -File dev/Start-Frontend.ps1
```

浏览器打开 **http://127.0.0.1:13000**。开发管理员用户名 `admin@local.test`；密码是本机 `dev/.env.local` 的 `DEV_ADMIN_PASSWORD`，仅在需要登录时本地查看。首次后端启动会自动初始化开发库并执行迁移。后端只监听 `127.0.0.1:18080`，本地配置及固定 JWT/TOTP 密钥留在 `dev/.runtime/data` 和 `dev/.env.local`；重启后继续使用相同凭据。

保存 Vue/TS/CSS 后，Vite 自动更新页面。保存后端 Go 或迁移 SQL 文件后，Air 自动重新编译并重启；编译失败时停止旧进程，修正后再次保存即可重建。修改依赖、启动脚本或配置后，手动 Ctrl+C 并重新执行对应启动命令。Windows 停止旧进程使用 Air 自身的 TASKKILL 行为。

脚本显式固定开发数据库、Redis、数据目录及 API 地址，并在退出时恢复调用进程的相关环境变量。前端 API 和 WebSocket 均指向本机；不要在开发后台添加正式上游凭据，避免发出真实付费请求。

## 停止与检查

两个窗口分别 Ctrl+C，然后停止数据库容器；此命令保留开发数据：

```powershell
docker compose --env-file dev/.env.local -f dev/compose.yml down
```

启动后可在第三个窗口检查：

```powershell
Invoke-RestMethod http://127.0.0.1:18080/health
Invoke-WebRequest http://127.0.0.1:13000 -UseBasicParsing
```

验收热更新时，修改一个页面文字并保存，确认浏览器显示新文字；修改一个后端 Go 文件并保存，确认 Air 输出重新构建和新的 `Server started`，再请求健康端点。最后撤销该验收改动。生产发布仍须通过 CI 构建与测试，开发热更新不等同于生产验收。

## 本次交付的验证范围

已完成 PowerShell 语法、TOML/YAML 解析和隔离脚本检查：使用临时目录与模拟的 Go/pnpm 命令，确认随机凭据生成、拒绝覆盖、固定本机端点和退出后环境恢复。交付时本机未安装 Go、Docker，尚未实际启动 Air、开发数据库或开发站点，也未完成保存文件触发后端重启及前端热更新的运行验收。工具齐备后应按上面的检查执行。
