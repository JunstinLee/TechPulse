# Access tokens for TechDistill

This guide explains how to obtain every **secret / credential** referenced in the project’s [`.env-example`](../.env-example) file. Copy values into a local `.env` file (never commit real tokens). For GitHub Actions, use encrypted [repository secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions) with names that match your workflow (see [`.github/workflows/prism-pipeline.yml`](../.github/workflows/prism-pipeline.yml)).

**How this project uses AI and Telegram**

- **AI is part of the intended workflow**, not an optional add-on: the pipeline collects sources, then produces **per-item AI commentary** and (with default settings) an **AI-generated overview** before reports are written. You need a working LLM provider (here: **OpenRouter** via `OPENROUTER_API_KEY`) for that full experience. The CLI still exposes `--no-ai` for exceptional or debugging runs only.
- **Telegram is required for the default GitHub Actions run**: [`.github/workflows/prism-pipeline.yml`](../.github/workflows/prism-pipeline.yml) runs `main.py` with **watch / Telegram push enabled by default** and does **not** upload `reports/` as workflow artifacts, so **`TG_BOT_TOKEN` and `TG_CHAT_ID` must be set as secrets** if you expect to receive outputs from scheduled or manual CI runs. Locally you can omit them only if you pass **`--no-watch`** and are satisfied reading files under `reports/`.

| Variable | Service | Role |
|----------|---------|------|
| `PH_API_TOKEN` | Product Hunt API v2 | Required (Product Hunt source) |
| `GITHUB_TOKEN` | GitHub | Strongly recommended (higher API rate limits) |
| `HF_TOKEN` | Hugging Face | Optional (better rate limits) |
| `OPENROUTER_API_KEY` | OpenRouter | **Required** for the full pipeline (AI commentary + overview) |
| `TG_BOT_TOKEN` | Telegram Bot API | **Required on GitHub Actions** (default workflow; primary delivery path). Optional locally with `--no-watch` |
| `TG_CHAT_ID` | Telegram | **Required on GitHub Actions** (pair with `TG_BOT_TOKEN`). Optional locally with `--no-watch` |

The following sections are **not** tokens: `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`, `OVERVIEW_*`, `AI_COMMENT_*`, `REPORT_WATCH_DIR`, etc. They are normal configuration; set them as needed without “obtaining” them from a provider.

---

## 1. `PH_API_TOKEN` (Product Hunt)

TechDistill calls the **Product Hunt GraphQL API** at `https://api.producthunt.com/v2/api/graphql` with:

`Authorization: Bearer <token>`

Official API hub: [Product Hunt API Documentation](https://api.producthunt.com/v2/docs).

### 1.1 Register an OAuth application

1. Sign in to [Product Hunt](https://www.producthunt.com/) with the account that should own the API app.
2. Open Product Hunt’s **developer / OAuth** section and **create an application** so you receive a **`client_id`** and **`client_secret`**.  
   - The exact menu path or URL can change; if you cannot find it, use the contact channel listed on the [official API docs](https://api.producthunt.com/v2/docs) (e.g. commercial or access questions).
3. Store `client_id` and `client_secret` securely. **Do not** commit them to git.

### 1.2 Get a bearer token (client credentials — typical for read-only public data)

For access **without a user context**, Product Hunt documents a **client-level** token via OAuth **client credentials**:

- **Endpoint:** `POST https://api.producthunt.com/v2/oauth/token`
- **Headers:** `Accept: application/json`, `Content-Type: application/json`
- **JSON body fields:**
  - `client_id` — your application id  
  - `client_secret` — your application secret  
  - `grant_type` — must be `client_credentials`

Documented request/response shape: [Ask for client level token](https://api.producthunt.com/v2/docs/oauth_client_only_authentication/oauth_token_ask_for_client_level_token).

The JSON response includes an **`access_token`** (and `token_type`, `scope`). Put **only** that **`access_token`** value in `PH_API_TOKEN`.

**Example (replace placeholders):**

```bash
curl -s -X POST "https://api.producthunt.com/v2/oauth/token" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_CLIENT_SECRET","grant_type":"client_credentials"}'
```

**Caveats (from Product Hunt docs):**

- A **client-level** token is for **public** endpoints that do not need user context. User-specific content may require **user OAuth** instead: [OAuth user authentication](https://api.producthunt.com/v2/docs/oauth_user_authentication/oauth_token_use_the_access_grant_code_you_received_through_the_redirect_to_request_an_access_token).
- If your dashboard exposes a single **developer token** that already works as `Bearer` for GraphQL, you may use that string as `PH_API_TOKEN`—but only if Product Hunt’s UI or docs say it is meant for API calls.

### 1.3 Call the GraphQL API (sanity check)

Official example headers for GraphQL: [Use the client level token for read API access](https://api.producthunt.com/v2/docs/oauth_client_only_authentication/oauth_test_use_the_client_level_token_for_read_api_access).

---

## 2. `GITHUB_TOKEN` (GitHub personal access token)

The GitHub spider uses the **GitHub REST API** (for example repository metadata and README). Unauthenticated requests are **heavily rate-limited**; a token raises limits and keeps the pipeline stable.

### 2.1 Create a token

1. Open GitHub in a browser and sign in.
2. Go to **Settings → Developer settings → Personal access tokens**.  
   Central doc: [Managing your personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).
3. Choose one type:
   - **Fine-grained personal access token** (recommended when it fits your use case): limit repositories and permissions.
   - **Personal access token (classic)**: broader legacy style; use minimal scopes if you must use classic.

### 2.2 Suggested permissions for TechDistill

TechDistill reads **public** trending data and READMEs via the API. Prefer the **smallest** permission set that still allows those endpoints to succeed:

- For **fine-grained** tokens: grant access appropriate to **public** repositories you need (org policies may vary) and include **read-only** permissions required for **Contents** / **Metadata** as needed for [`GET /repos/{owner}/{repo}/readme`](https://docs.github.com/en/rest/repos/contents#get-a-repository-readme) and related calls. Adjust if GitHub returns `403` for a specific endpoint.
- Avoid granting **write** or **admin** scopes unless you have a separate operational need.

### 2.3 Use the token in this project

- Local: set `GITHUB_TOKEN=<your PAT>` in `.env`.
- GitHub Actions: many workflows store the PAT in a secret named `GH_TOKEN` and map it to the environment variable `GITHUB_TOKEN` (avoid confusing it with the **built-in** `GITHUB_TOKEN` workflow credential unless you intentionally use that). Follow the comments in your workflow file.

**Security:** Treat the PAT like a password; rotate it if leaked.

---

## 3. `HF_TOKEN` (Hugging Face user access token — optional)

Used to authenticate to Hugging Face services and **improve rate limits** when the pipeline hits Hugging Face APIs.

### 3.1 Create a token

1. Open [Hugging Face Settings → Access Tokens](https://huggingface.co/settings/tokens).
2. Click **New token**.
3. Choose a **name** and a **role**:
   - **`read`** — read Hub content you can already read (typical for download / inference-style use).
   - **`write`** — read plus push for repos you can write to.
   - **`fine-grained`** — restrict to specific resources (recommended for production minimization of blast radius).

Official documentation: [User access tokens](https://huggingface.co/docs/hub/security-tokens).

### 3.2 Use in this project

Set `HF_TOKEN=<token>` in `.env`. If unused, you can omit it or leave empty depending on your config; behavior matches the optional note in `.env-example`.

---

## 4. `OPENROUTER_API_KEY` (OpenRouter)

TechDistill’s AI path talks to an **OpenAI-compatible** HTTP API and is **central to the product workflow**: without it you do not get the de-noised per-source comments or the AI overview that the Markdown reports are built around (you would have to run with `--no-ai`). The default base URL is `https://openrouter.ai/api/v1` (see `.env-example`).

### 4.1 Create an API key

1. Sign in at [OpenRouter](https://openrouter.ai/).
2. Open **[API Keys](https://openrouter.ai/keys)** and create a key (you can name it and optionally set a spend limit).
3. Authentication for requests: **`Authorization: Bearer <OPENROUTER_API_KEY>`**.

Official reference: [API Authentication](https://openrouter.ai/docs/api/reference/authentication).

### 4.2 Management API keys (do not confuse)

OpenRouter also documents **Management API keys** for **creating or administering** other keys programmatically. Those keys are **not** for ordinary chat/completions traffic. Use a normal **API key** from the keys page for `OPENROUTER_API_KEY`. Details: same authentication doc, *Management API Keys* section.

### 4.3 Optional request headers

OpenRouter’s docs mention optional headers such as `HTTP-Referer` and `X-OpenRouter-Title` for rankings or attribution. TechDistill may not set them; add them in your HTTP client only if you need them.

If your gateway needs extra JSON fields on `chat/completions`, some deployments use `OPENROUTER_CHAT_COMPLETIONS_EXTRA_JSON` (see workflow comments)—that value is optional and must be valid JSON if set.

---

## 5. `TG_BOT_TOKEN` (Telegram bot)

Required for **GitHub Actions** when using the default [`prism-pipeline.yml`](../.github/workflows/prism-pipeline.yml): configure **`TG_BOT_TOKEN`** (and **`TG_CHAT_ID`**) as repository secrets so the run can push reports after generation. Locally, Telegram is optional if you run **`python main.py --no-watch`** and only need files in `reports/`.

### 5.1 Create a bot and get the token

1. In Telegram, open a chat with [**@BotFather**](https://t.me/botfather).
2. Send **`/newbot`** and follow prompts (name and username for the bot).
3. BotFather returns a **token** (format similar to `123456789:AA...`).

Official tutorial: [*Obtain Your Bot Token*](https://core.telegram.org/bots/tutorial) (Telegram **Core** documentation).

### 5.2 Store safely

Put the token in `TG_BOT_TOKEN`. **Never** publish it in screenshots, logs, or public repositories.

---

## 6. `TG_CHAT_ID` (Telegram chat identifier)

Same delivery rules as **section 5**: **required** together with `TG_BOT_TOKEN` for the default **GitHub Actions** workflow; optional locally when using **`--no-watch`**. The bot must know **which chat** to send messages to (private chat with you, a group, or a channel, depending on your setup).

### 6.1 Private chat (common)

1. Start your bot (send `/start` or any message) so your user appears in updates.
2. Retrieve updates once, for example in a browser or with `curl` (replace `TOKEN`):

   `https://api.telegram.org/bot<TOKEN>/getUpdates`

3. In the JSON, locate `message.chat.id` (or channel/group variants). That numeric (or prefixed) id is what you usually put in `TG_CHAT_ID`.

### 6.2 Groups and channels

For groups or channels, the bot often must be **added** and allowed to **post**. Chat ids for groups are often **negative** integers. See the [Telegram Bot API](https://core.telegram.org/bots/api) for the object shapes (`chat`, `message`, etc.).

### 6.3 Operational note

Users must usually **initiate** contact with the bot (or satisfy Telegram’s rules for bots in groups) before the bot can message them.

---

## 7. Checklist before running TechDistill

- [ ] `.env` created from `.env-example`; all variables required for *your* run mode are filled.
- [ ] No real tokens committed (`git` ignores `.env`).
- [ ] `PH_API_TOKEN` is a **Bearer** access token that works with Product Hunt GraphQL.
- [ ] `GITHUB_TOKEN` has **minimal** permissions for your API usage.
- [ ] `OPENROUTER_API_KEY` is set for the **full AI workflow** (a normal OpenRouter **API** key, not a management-only key), unless you intentionally use `--no-ai`.
- [ ] For **GitHub Actions**: **`TG_BOT_TOKEN` and `TG_CHAT_ID` secrets** are configured matching [`prism-pipeline.yml`](../.github/workflows/prism-pipeline.yml) (both are mandatory for the default CI delivery path).
- [ ] For **local** push: same Telegram pair; if you skip Telegram, run with **`--no-watch`** and collect outputs from `reports/` yourself.

---

## 8. Further reading (official)

- Product Hunt API: [https://api.producthunt.com/v2/docs](https://api.producthunt.com/v2/docs)
- GitHub PATs: [https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- Hugging Face tokens: [https://huggingface.co/docs/hub/security-tokens](https://huggingface.co/docs/hub/security-tokens)
- OpenRouter auth: [https://openrouter.ai/docs/api/reference/authentication](https://openrouter.ai/docs/api/reference/authentication)
- Telegram bots: [https://core.telegram.org/bots/tutorial](https://core.telegram.org/bots/tutorial)

---

*This file was written for the TechDistill repository. Product menus, URLs, and OAuth dashboards may change; when in doubt, rely on the official documentation linked above.*
