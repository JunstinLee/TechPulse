# TechDistill 访问令牌获取指南

本文说明如何获取项目中 [`.env-example`](../.env-example) 所列的每一项**密钥 / 凭证**。请将值写入本地 `.env`（切勿提交真实令牌）。若在 GitHub Actions 中运行，请使用加密的 [仓库 Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)，名称需与工作流一致（参见 [`.github/workflows/prism-pipeline.yml`](../.github/workflows/prism-pipeline.yml)）。

**本项目中 AI 与 Telegram 的定位**

- **AI 是既定工作流的核心环节**，而非可有可无的开关：流水线在汇总各数据源后，会生成**逐条 AI 点评**，并在默认配置下生成 **AI 总览**，再写入 Markdown 报告。要完整跑通这一体验，需要可用的 LLM 服务（本项目通过 **OpenRouter**，即 `OPENROUTER_API_KEY`）。命令行仍提供 `--no-ai`，仅建议用于异常排查或特殊场景。
- **在默认的 GitHub Actions 工作流中，Telegram 属于必配项**：[`.github/workflows/prism-pipeline.yml`](../.github/workflows/prism-pipeline.yml) 默认执行带 **watch / Telegram 推送** 的 `main.py`，且**不会**把 `reports/` 作为工作流产物上传，因此若依赖定时或手动 CI 产出，必须在仓库 Secrets 中配置 **`TG_BOT_TOKEN` 与 `TG_CHAT_ID`**。本机若不需要推送，可改用 **`python main.py --no-watch`**，并自行查看 `reports/` 下的文件。

| 变量 | 服务 | 说明 |
|----------|---------|------|
| `PH_API_TOKEN` | Product Hunt API v2 | 必需（Product Hunt 数据源） |
| `GITHUB_TOKEN` | GitHub | 强烈建议（提高 API 速率上限） |
| `HF_TOKEN` | Hugging Face | 可选（改善速率限制） |
| `OPENROUTER_API_KEY` | OpenRouter | **完整流水线必需**（AI 点评 + 总览） |
| `TG_BOT_TOKEN` | Telegram Bot API | **GitHub Actions 默认工作流下必需**（主要结果投递路径）。本机可用 `--no-watch` 时不配 |
| `TG_CHAT_ID` | Telegram | **GitHub Actions 默认工作流下必需**（与 `TG_BOT_TOKEN` 成对）。本机可用 `--no-watch` 时不配 |

以下**不是**令牌：`OPENROUTER_BASE_URL`、`OPENROUTER_MODEL`、`OVERVIEW_*`、`AI_COMMENT_*`、`REPORT_WATCH_DIR` 等，它们为普通配置项，按需填写即可，无需向服务商「申请令牌」。

---

## 1. `PH_API_TOKEN`（Product Hunt）

TechDistill 通过如下方式调用 **Product Hunt GraphQL API** `https://api.producthunt.com/v2/api/graphql`：

`Authorization: Bearer <token>`

官方 API 中心：[Product Hunt API Documentation](https://api.producthunt.com/v2/docs)。

### 1.1 注册 OAuth 应用

1. 使用将拥有该 API 应用的账号登录 [Product Hunt](https://www.producthunt.com/)。
2. 打开 Product Hunt 的 **开发者 / OAuth** 相关页面，**创建应用**，获得 **`client_id`** 与 **`client_secret`**。  
   - 具体菜单路径或 URL 可能变更；若找不到，请使用 [官方 API 文档](https://api.producthunt.com/v2/docs) 中列出的联系或说明渠道（如商务或访问权限问题）。
3. 安全保存 `client_id` 与 `client_secret`，**不要**提交到 git。

### 1.2 获取 Bearer 令牌（client credentials — 只读公开数据的常见方式）

在**无需用户上下文**的访问场景下，Product Hunt 文档说明可通过 OAuth **client credentials** 换取 **client 级别**令牌：

- **端点：** `POST https://api.producthunt.com/v2/oauth/token`
- **请求头：** `Accept: application/json`、`Content-Type: application/json`
- **JSON 体字段：**
  - `client_id` — 应用 id  
  - `client_secret` — 应用密钥  
  - `grant_type` — 必须为 `client_credentials`

请求与响应格式见：[Ask for client level token](https://api.producthunt.com/v2/docs/oauth_client_only_authentication/oauth_token_ask_for_client_level_token)。

响应 JSON 中的 **`access_token`**（以及 `token_type`、`scope`）即为所需；请**仅**将 **`access_token`** 填入 `PH_API_TOKEN`。

**示例（替换占位符）：**

```bash
curl -s -X POST "https://api.producthunt.com/v2/oauth/token" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_CLIENT_SECRET","grant_type":"client_credentials"}'
```

**注意事项（摘自 Product Hunt 文档）：**

- **Client 级别**令牌适用于**不需要用户上下文**的 **公开**接口。若需用户维度数据，应改用 **用户 OAuth**：[OAuth user authentication](https://api.producthunt.com/v2/docs/oauth_user_authentication/oauth_token_use_the_access_grant_code_you_received_through_the_redirect_to_request_an_access_token)。
- 若控制台提供可直接用于 GraphQL 的 **`Bearer` 开发者令牌**（developer token），且官方界面或文档写明用于 API，也可将其作为 `PH_API_TOKEN` 使用。

### 1.3 调用 GraphQL API（自检）

官方 GraphQL 请求头示例：[Use the client level token for read API access](https://api.producthunt.com/v2/docs/oauth_client_only_authentication/oauth_test_use_the_client_level_token_for_read_api_access)。

---

## 2. `GITHUB_TOKEN`（GitHub 个人访问令牌）

GitHub 爬虫使用 **GitHub REST API**（例如仓库元数据、README）。未认证请求**速率限制很严**；使用令牌可提高上限，流水线更稳定。

### 2.1 创建令牌

1. 浏览器登录 GitHub。
2. 进入 **Settings → Developer settings → Personal access tokens**。  
   总文档：[Managing your personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)。
3. 选择一种类型：
   - **Fine-grained personal access token**（在适用时推荐）：可限定仓库与权限。
   - **Personal access token (classic)**：传统宽权限方式；若必须用 classic，请尽量选最小 scope。

### 2.2 TechDistill 建议权限

项目通过 API 读取**公开** trending 与 README。在满足接口成功的前提下，优先选**最小**权限集：

- **Fine-grained**：按你对**公开**仓库的访问需求授权（组织策略可能不同），并为 [`GET /repos/{owner}/{repo}/readme`](https://docs.github.com/en/rest/repos/contents#get-a-repository-readme) 等调用赋予所需的 **Contents** / **Metadata** 等**只读**权限。若某端点返回 `403` 再酌情收紧或放宽。
- 除非另有运维需求，避免给予 **write** 或 **admin** 级别权限。

### 2.3 在本项目中的用法

- 本地：在 `.env` 中设置 `GITHUB_TOKEN=<你的 PAT>`。
- GitHub Actions：不少工作流将 PAT 存为名为 `GH_TOKEN` 的 secret，再映射到环境变量 `GITHUB_TOKEN`（除非有意使用，否则勿与 workflow **内置**的 `GITHUB_TOKEN` 混淆）。具体以工作流文件内注释为准。

**安全：** PAT 视同密码；若泄露请及时轮换。

---

## 3. `HF_TOKEN`（Hugging Face 用户访问令牌 — 可选）

用于访问 Hugging Face 服务，在流水线请求 HF API 时**改善速率限制**。

### 3.1 创建令牌

1. 打开 [Hugging Face 设置 → Access Tokens](https://huggingface.co/settings/tokens)。
2. 点击 **New token**。
3. 填写 **名称** 并选择 **角色**：
   - **`read`** — 只读你有权访问的 Hub 内容（常见于下载/推理类用法）。
   - **`write`** — 在读基础上，还可向你拥有写权限的仓库推送。
   - **`fine-grained`** — 限定到具体资源（生产环境建议，缩小泄露影响面）。

官方文档：[User access tokens](https://huggingface.co/docs/hub/security-tokens)。

### 3.2 在本项目中的用法

在 `.env` 中设置 `HF_TOKEN=<token>`。若不使用，可按配置省略或留空，行为与 `.env-example` 中的「可选」说明一致。

---

## 4. `OPENROUTER_API_KEY`（OpenRouter）

TechDistill 通过 **OpenAI 兼容** HTTP API 调用大模型，且这一路径是**工作流主轴**：没有有效密钥时无法得到设计中的「降噪」逐条点评与 AI 总览，报告会失去核心信息（除非刻意使用 `--no-ai`）。默认基址为 `https://openrouter.ai/api/v1`（见 `.env-example`）。

### 4.1 创建 API 密钥

1. 登录 [OpenRouter](https://openrouter.ai/)。
2. 打开 **[API Keys](https://openrouter.ai/keys)** 创建密钥（可命名并可设消费上限）。
3. 请求认证方式：**`Authorization: Bearer <OPENROUTER_API_KEY>`**。

官方说明：[API Authentication](https://openrouter.ai/docs/api/reference/authentication)。

### 4.2 Management API keys（勿混淆）

OpenRouter 还文档化了 **Management API keys**，用于**以编程方式创建或管理**其他密钥，**不能**用于普通 **聊天补全**流量。`OPENROUTER_API_KEY` 应使用 keys 页面创建的**普通 API key**。详见同一认证文档中的 *Management API Keys* 小节。

### 4.3 可选请求头

OpenRouter 文档提到可选头如 `HTTP-Referer`、`X-OpenRouter-Title`（排行或归属展示）。TechDistill 未必设置；若你需要可在 HTTP 客户端自行添加。

若网关要求在 `chat/completions` 上附加额外 JSON 字段，部分部署会使用 `OPENROUTER_CHAT_COMPLETIONS_EXTRA_JSON`（见工作流注释）；该变量可选，若设置须为合法 JSON。

---

## 5. `TG_BOT_TOKEN`（Telegram 机器人）

使用默认的 [`prism-pipeline.yml`](../.github/workflows/prism-pipeline.yml) 在 **GitHub Actions** 上运行时，必须在仓库 Secrets 中配置 **`TG_BOT_TOKEN`**（及 **`TG_CHAT_ID`**），以便生成报告后推送。本机若不需要推送，可执行 **`python main.py --no-watch`**，仅使用 `reports/` 目录中的文件即可。

### 5.1 创建机器人并获取 token

1. 在 Telegram 中与 [**@BotFather**](https://t.me/botfather) 对话。
2. 发送 **`/newbot`**，按提示设置机器人显示名与用户名。
3. BotFather 返回 **token**（形如 `123456789:AA...`）。

官方教程：[《Obtain Your Bot Token》](https://core.telegram.org/bots/tutorial)（Telegram **Core** 文档）。

### 5.2 安全保存

将 token 写入 `TG_BOT_TOKEN`。**切勿**在截图、日志或公开仓库中泄露。

---

## 6. `TG_CHAT_ID`（Telegram 会话标识）

与**第 5 节**投递规则一致：**GitHub Actions** 默认工作流下必须与 `TG_BOT_TOKEN` **同时**配置；本机使用 **`--no-watch`** 时可不配置。机器人需知道向**哪个会话**发消息（取决于你的配置：私聊、群组或频道）。

### 6.1 私聊（常见）

1. 先与机器人对话（发送 `/start` 或任意消息），使你的用户出现在更新里。
2. 拉取一次更新，例如在浏览器或使用 `curl`（替换 `TOKEN`）：

   `https://api.telegram.org/bot<TOKEN>/getUpdates`

3. 在返回的 JSON 中找到 `message.chat.id`（或频道/群组对应字段）。该数字（或带前缀的 id）通常即为 `TG_CHAT_ID`。

### 6.2 群组与频道

群组或频道中通常需**添加**机器人并允许**发言**。群组的 chat id 常为**负**整数。对象结构见 [Telegram Bot API](https://core.telegram.org/bots/api)（`chat`、`message` 等）。

### 6.3 运营提示

在多数场景下，用户需**主动**联络机器人（或满足 Telegram 对群内机器人的规则），机器人才便于向其发消息。

---

## 7. 运行 TechDistill 前检查清单

- [ ] 已根据 `.env-example` 创建 `.env`，且按你的运行方式填齐**所需**变量。
- [ ] 未将真实令牌提交进 git（`.env` 已被忽略）。
- [ ] `PH_API_TOKEN` 为可在 Product Hunt GraphQL 下使用的 **Bearer** access token。
- [ ] `GITHUB_TOKEN` 对你实际调用的 API **权限最小化**。
- [ ] 若跑**完整 AI 工作流**：已配置 `OPENROUTER_API_KEY`（OpenRouter **普通** API key，非仅管理用途的 Management key）；若刻意禁用 AI，则使用 `--no-ai`。
- [ ] **GitHub Actions**：已按 [`prism-pipeline.yml`](../.github/workflows/prism-pipeline.yml) 配置 **`TG_BOT_TOKEN` 与 `TG_CHAT_ID` 两项 Secrets**（默认 CI 投递路径下二者均为必选项）。
- [ ] **本机**需要推送时：同样配对配置 Telegram；不需要推送时使用 **`--no-watch`**，并自行从 `reports/` 取结果。

---

## 8. 延伸阅读（官方）

- Product Hunt API: [https://api.producthunt.com/v2/docs](https://api.producthunt.com/v2/docs)
- GitHub PAT: [https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- Hugging Face tokens: [https://huggingface.co/docs/hub/security-tokens](https://huggingface.co/docs/hub/security-tokens)
- OpenRouter 认证: [https://openrouter.ai/docs/api/reference/authentication](https://openrouter.ai/docs/api/reference/authentication)
- Telegram 机器人: [https://core.telegram.org/bots/tutorial](https://core.telegram.org/bots/tutorial)

---

*本文为 TechDistill 仓库撰写。产品菜单、URL 与 OAuth 后台可能变更；如有出入，以上方官方文档为准。*
