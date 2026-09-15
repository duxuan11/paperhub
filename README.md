# PaperHub

面向科研人员的本地化科研 AI 工作平台：**论文 → AI 分析 → 微信公众号文章**。

把 PDF 论文扔进去，通过 Web、Chat 或 CLI 告诉 AI「读一下这篇论文」「分析 Figure 3」「写成公众号文章」，PaperHub 自动完成解析、结构化、Figure 检测、AI 分析与内容生成，并安全地发送到微信公众号草稿箱。

> 当前为 MVP 版本：只实现微信公众号，未实现小红书 / X / 知乎等平台。

---

## 功能总览

- 论文批量上传、管理、状态机跟踪
- PDF → MinerU 解析 → 结构化 Markdown + 图片
- YOLO Figure 检测（可配置模型 / 无模型时启发式降级）
- 三栏论文阅读器（目录 / Markdown / AI 助手问答）
- AI 分析：论文级配置 Skills / Model / Custom Prompt，基于 MinerU 结果逐 Skill 生成结构化结果
- AI Chat（自由问答 + 阅读器内论文问答；OpenAI-compatible，默认 DeepSeek，无 Key 时 Mock）
- Skill 系统（内置 paper-summary / figure-analysis / wechat-article / 等）+ 自定义 Skill（设置页新建 / 覆盖内置 / 删除）
- 微信公众号文章生成（8 套精致排版模板，支持自定义主题）+ 三栏编辑器
- 微信公众号草稿箱发布（安全设计：默认不直接发布）
- MCP Server（接入 Open WebUI / Claude 等 Agent）
- Typer CLI（`paperhub`）
- 完整 Docker Compose 部署 + 原生本地运行

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS |
| 后端 | Python · FastAPI · SQLAlchemy 2 (async) |
| 数据库 | PostgreSQL |
| 队列 | Redis + Arq |
| 存储 | MinIO（S3 兼容） |
| AI | Open WebUI · OpenAI-compatible API（OpenAI / DeepSeek / Ollama / …） |
| PDF | MinerU（远程 API / Mock：PyMuPDF 本地解析） |
| 视觉 | Ultralytics YOLO（可配置权重 / 启发式降级） |
| 部署 | Docker Compose |
| CLI | Typer |
| API | REST + SSE |

## 架构

```
            ┌──────────────┐
            │   Next.js    │  Web UI
            └──────┬───────┘
                   │ /api/proxy
            ┌──────▼───────┐
            │   FastAPI    │  PaperHub API
            └──────┬───────┘
   ┌───────────────┼───────────────┐
   ▼               ▼               ▼
PostgreSQL      Redis           MinIO
                   ▼
                Worker (Arq)
                ┌──┴──┐
                ▼     ▼
             MinerU  YOLO
                └──┬──┘
           Markdown + Figures
                   │
                   ▼
           ┌───────────────┐
           │  Open WebUI   │ Chat / Agent
           └───────┬───────┘
                   │ MCP
           ┌───────▼───────┐
           │ PaperHub MCP  │
           └───────┬───────┘
                   ▼
            WeChat Publisher
```

**职责划分**：PaperHub 负责论文管理、MinerU 调用、Figure 检测、Markdown 管理、任务管理、公众号内容生成与发布、API / CLI / MCP。Chat / Agent / 模型调用 / 对话历史 / Knowledge / Tool / Skill 复用 Open WebUI；页面内 Chat 则通过 PaperHub 自带 LLM 客户端直接调用 OpenAI-compatible API。

## 目录结构

```
paperhub/
├─ docker-compose.yml
├─ .env.example            # 所有配置项模板
├─ README.md
├─ Makefile
├─ backend/                # FastAPI + Arq Worker
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/             # config / db / redis / minio / security / logging
│  │  ├─ models/           # SQLAlchemy 模型
│  │  ├─ repositories/     # 数据访问
│  │  ├─ services/         # mineru / yolo / llm / chat / article / paper / wechat / skill
│  │  ├─ api/v1/           # REST 路由
│  │  └─ workers/          # Arq 任务
│  └─ tests/
├─ frontend/               # Next.js
│  ├─ app/                 # 页面 + /api/proxy 代理
│  ├─ components/
│  └─ lib/
├─ mcp-server/             # MCP Server（stdio / streamable-http）
├─ cli/                    # paperhub Typer CLI
├─ publishers/wechat/      # client / formatter / publisher（可扩展其它平台）
├─ skills/                 # Markdown Skill 定义
├─ models/                 # YOLO 权重目录
├─ data/                   # 本地数据
├─ demo/                   # demo 论文 PDF
└─ scripts/                # 启动/引导/演示脚本
```

## 环境要求

- 方式 A（Docker）：Docker + Docker Compose v2
- 方式 B（原生）：Ubuntu / WSL2 · Python 3.11+ · `uv` · Node 20+（或 nvm）· 网络可访问 pypi / npm / dl.min.io

## 快速开始（从零到运行）

### 方式 A：Docker Compose

```bash
cp .env.example .env      # 按需填写 Key（不填则用 Mock）
docker compose up -d
# 打开 http://localhost:3000
```

首次启动会拉取镜像。后端自动建表，MinIO 自动建桶。

### 方式 B：原生本地运行（无需 Docker / 无需 sudo）

本仓库提供了无需 sudo 的原生引导，所有依赖安装到 `~/paperhub-runtime`。

```bash
# 1. 下载并解压 PostgreSQL/Redis/MinIO 二进制 + 启动服务 + 建库
make bootstrap

# 2. 启动后端（终端 1）
make backend

# 3. 启动 Worker（终端 2）
make worker

# 4. 启动前端（终端 3，自动使用 nvm node 25）
make frontend
# 打开 http://localhost:3000
```

> `make bootstrap` 会在 `~/.apttmp` 刷新 apt 索引、下载 deb 包并解压到 `~/paperhub-runtime`，完全用户空间运行，不需要 root。PostgreSQL 数据目录放在 Linux 文件系统（`~/paperhub-runtime/postgres`）以规避 WSL `/mnt/d` 的权限限制。

## 端到端演示

```bash
make demo
```

该脚本演示完整链路：上传 `demo/paper.pdf` → MinerU 解析 → Figure 检测 → Chat 总结 → Chat 分析 Figure → 生成公众号文章 → 发送草稿箱 → CLI 状态。

## MinerU 配置

默认使用 `MockMinerUService`（PyMuPDF 本地解析，无需 Key，可直接跑通流程）。

```env
MINERU_API_URL=https://your-mineru-endpoint
MINERU_API_KEY=your-key
```

填写后自动切换为真实 MinerU API（`RemoteMinerUService`）。也可以在 `docker-compose.yml` 中取消注释本地 `mineru` 服务（需 GPU）。

## YOLO 配置

```env
YOLO_ENABLED=true
YOLO_MODEL_PATH=./models/best.onnx
```

把训练好的 Figure 检测权重（ONNX 格式）放到 `models/` 后启用即可。YOLO 的输入是**整页 PDF 渲染图**（PyMuPDF 渲染），在整页上框出 Figure 后裁剪保存，不再依赖 MinerU 切出的小图；MinerU 仍负责 markdown 文本与正文内嵌图片。

- 依赖：`cd backend && uv sync --extra yolo`（onnxruntime + opencv-python-headless，无需 ultralytics / torch）
- 检测为空（如权重未训练/低置信度）时自动回退为「按 markdown 顺序的内嵌图片」作为 Figure，保证下游流程可用。
- 未配置 `YOLO_ENABLED`/`YOLO_MODEL_PATH` 时使用回退路径（HeuristicFigureService），无模型也能跑通。

## LLM 配置（OpenAI-compatible）

默认 DeepSeek，不写死厂商：

```env
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

支持任意 OpenAI-compatible 端点：OpenAI / DeepSeek / Gemini-compatible / 本地 Ollama（`OPENAI_BASE_URL=http://localhost:11434/v1`）。**未配置 Key 时使用 MockLLMService**，仍可完整演示。

## Open WebUI 配置

`docker compose up -d` 会一并启动 Open WebUI（http://localhost:8080）。

在 Open WebUI 中接入 PaperHub MCP Server：`设置 → 连接 → MCP Servers`，添加一个 **Streamable HTTP** 类型：

- 类型：`Streamable HTTP`
- URL：`http://mcp-server:8001/mcp`（Open WebUI 与 MCP Server 同在 compose 网络内）

说明：compose 中的 `mcp-server` 服务以常驻 HTTP 模式运行（`MCP_TRANSPORT=streamable-http`，监听 `8001`）。
若要改为 stdio 模式由客户端直接拉起，可设置 `MCP_TRANSPORT=stdio`，但此时它不应作为 compose 常驻服务（否则会因 stdin 关闭而退出并触发重启循环）。

MCP 工具：`search_papers` / `get_paper` / `get_paper_markdown` / `get_paper_metadata` / `get_paper_figures` / `get_figure` / `search_paper_content` / `analyze_paper` / `generate_wechat_article` / `publish_wechat`。

## 微信公众号配置

```env
WECHAT_APP_ID=your-appid
WECHAT_APP_SECRET=your-secret
# 可选：草稿封面用的永久素材 media_id（留空则自动上传首图/内置封面并缓存）
WECHAT_THUMB_MEDIA_ID=
```

填写后使用 `RealWeChatPublisher`（调用 `draft/add` 创建草稿）；未配置使用 Mock 记录。

### 真实发送的前置条件（缺一不可）

1. **IP 白名单**：公众号后台 → 设置与开发 → 基本配置 → IP白名单，加入运行 Worker 的机器/主机的
   **公网出口 IP**。未加白名单时微信返回 `errcode=40164 invalid ip ... not in whitelist`，
   草稿箱里不会有任何内容（Docker 与原生共用宿主机出口 IP）。
2. **接口权限**：账号需开通草稿箱与发布功能（未开通时报 `48001 / 53503 / 53504`）。
3. **封面图**：图文草稿的 `thumb_media_id` 必填。PaperHub 会自动把文章首图（无配图时用内置渐变封面）
   上传为永久素材并缓存到 Redis，也可用 `WECHAT_THUMB_MEDIA_ID` 指定已有素材。
4. **正文图片**：正文中的 `{{figure:N}}` 会自动上传到微信（`media/uploadimg`）并替换为 mmbiz URL；
   微信访问不到 localhost/MinIO 地址，跳过这一步图片不会显示。

### 推送结果怎么看

推送是异步任务：接口只负责入队，结果通过 `GET /api/v1/wechat/records?article_id=<id>` 查询。

- 前端文章编辑器：提交后自动轮询，工具栏下方显示「上次推送 成功/失败 + 错误原因」。
- CLI：`paperhub publish-wechat PAPER_ID` 会等待并打印真实结果（失败时退出码非 0）。
- 「任务」页可看到 `publish_wechat` 任务的状态与 error。

**安全设计**：默认只「发送到公众号草稿箱」，不直接发布；页面提供 [保存草稿] / [发送到草稿箱] / [发布] 三级操作，发布需公众号 API 权限。

## CLI 使用

```bash
cd cli && uv tool install --force .   # 或 cd cli && uv run paperhub ...

paperhub upload paper.pdf
paperhub upload ./papers/*.pdf
paperhub list
paperhub status PAPER_ID
paperhub analyze PAPER_ID
paperhub summarize PAPER_ID
paperhub generate-wechat PAPER_ID --style "科研论文解读"
paperhub publish-wechat PAPER_ID
paperhub ask PAPER_ID "这篇论文的核心创新是什么？"
paperhub agent "分析我最近上传的5篇论文"
paperhub config set api-key xxx
paperhub config set base-url http://localhost:8000
paperhub config show
```

CLI 通过 REST API 与后端通信，不直接操作数据库。

## API 使用

Swagger / OpenAPI：http://localhost:8000/docs

主要端点（前缀 `/api/v1`）：

```
POST   /papers/upload                 # 单篇上传
POST   /papers/batch-upload           # 批量上传
GET    /papers                        # 列表
GET    /papers/{id}                   # 详情
GET    /papers/{id}/markdown          # Markdown
GET    /papers/{id}/figures           # Figure 列表
GET    /papers/{id}/analysis          # AI 分析汇总文本（兼容）
GET    /papers/{id}/ai-analysis       # AI 分析配置 + 分 Skill 结果
PUT    /papers/{id}/ai-analysis/config # 保存 Skills/Model/Prompt 配置
POST   /papers/{id}/ai-analysis/run   # 执行 AI 分析（需 MinerU 已解析）
POST   /papers/{id}/parse             # 重新解析
POST   /papers/{id}/detect-figures    # 重新检测
POST   /papers/{id}/analyze           # AI 分析
POST   /papers/{id}/generate-wechat   # 生成公众号文章
GET    /jobs  /jobs/{id}              # 任务
GET    /articles  /articles/{id}      # 文章
PATCH  /articles/{id}                 # 保存草稿
POST   /articles/{id}/action          # 润色/缩短/扩展/重新生成
POST   /wechat/draft                  # 发送草稿箱
POST   /wechat/publish                # 正式发布
POST   /chat                          # SSE 流式对话
POST   /agent                         # 自由 Agent（带入最近论文）
GET    /files/{key}                   # 图片/文件代理
GET    /skills                        # 可用 Skill 列表（内置 + 自定义）
POST   /skills                        # 新建自定义 Skill（同名即覆盖内置）
GET    /skills/{name}                 # Skill 详情（含正文）
PUT    /skills/{name}                 # 修改自定义 Skill
DELETE /skills/{name}                 # 删除自定义 Skill（恢复内置）
GET    /health  /settings             # 元信息
```

鉴权：设置 `PAPERHUB_API_KEY` 后，需携带 `Authorization: Bearer *** 用 `paperhub config set api-key xxx`）。留空则开发模式不鉴权。

## 论文状态机

```
UPLOADED → PARSING → PARSED → FIGURE_DETECTING → READY
                                              → ANALYZING → ANALYZED
                                              → CONTENT_GENERATED → PUBLISHED
任意环节失败 → FAILED（数据保留，可重试）
```

## 开发环境

```bash
# 后端
cd backend && uv sync && uv run uvicorn app.main:app --reload
# Worker
cd backend && uv run arq app.workers.main.WorkerSettings
# 前端
cd frontend && nvm use 25 && npm install && npm run dev
# 测试
cd backend && uv run pytest -q
# MCP（默认 stdio；常驻 HTTP 模式见下）
cd mcp-server && uv sync && uv run python server.py
# MCP（streamable-http，监听 http://localhost:8001/mcp）
cd mcp-server && MCP_TRANSPORT=streamable-http MCP_PORT=8001 uv run python server.py
```

## 常见问题

**Q：没有 API Key 能跑吗？**
能。MinerU / YOLO / LLM / 微信公众号均为「真实实现 + Mock 实现」双模式，未配置 Key 时自动降级，全流程可演示。

**Q：WSL 下 PostgreSQL 起不来（invalid permissions）？**
`/mnt/d`（drvfs）无法设置 0700 权限。本仓库原生引导把 PostgreSQL 数据目录放到 `~/paperhub-runtime`（Linux 文件系统），已规避此问题。

**Q：上传后一直 PARSING？**
检查 Worker 是否启动（`make worker`），以及 `docker compose logs -f worker` / `tail /tmp/paperhub-worker.log`。

**Q：点了「发送到草稿箱 / 发布」公众号里什么都没有？**
先看文章编辑器工具栏下方的「上次推送」或 `GET /api/v1/wechat/records?article_id=<id>` 的 `error`：
- `errcode=40164 ... not in whitelist`：调用方公网出口 IP 未加入公众号 IP 白名单（最常见）。
- `errcode=40007 invalid media_id`：封面素材非法，检查 `WECHAT_THUMB_MEDIA_ID`。
- `errcode=48001 / 53503 / 53504`：账号未开通对应接口权限，或未认证。
默认只创建草稿；正式发布（`freepublish/submit`）需要公众号具备发布权限。

**Q：前端访问后端失败？**
前端通过 `/api/proxy` 转发到 `BACKEND_URL`（默认 `http://localhost:8000`）。Docker 下已配置为 `http://backend:8000`。

## 已知说明（MVP）

- 数据库用启动时 `create_all` 建表，生产环境可替换为 Alembic 迁移。
- Next.js 15.5.4 存在若干上游安全通告（不影响本地 MVP 使用），生产部署建议升级至已修复版本。
- Figure 分析当前基于论文文字描述，多模态图像识别需配置具备视觉能力的 LLM。
