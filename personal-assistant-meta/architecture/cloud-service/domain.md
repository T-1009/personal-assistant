# Domain — 自定义域名与 OBS 静态网站托管（Legacy）

> 版本：v1.0 | 状态：Legacy | 关联文档：[`ADR-017`](../ADR/ADR-017-cloudflare-pages-proxy.md)

> Production Web Chat 已迁移到
> `https://agentarts-personal-assistant.pages.dev`。本文记录的 OBS、
> `chat.resource-governance.cloud` 和旧 GitHub Actions 流程不再用于当前
> Production deployment，仅作为历史基础设施与未来自定义域名参考。

---

## 1. 为什么需要自定义域名

华为云 OBS 对默认域名（`*.obs-website.cn-southwest-2.myhuaweicloud.com`）有安全合规限制：

> 浏览器访问 `.html` 等网页文件时，OBS 网关层**强制注入 `Content-Disposition: attachment`**，导致浏览器下载文件而非渲染页面。

这是防钓鱼/挂马的安全策略，无法关闭。**唯一解决方案：绑定自有域名。**

| 域名类型 | 浏览器行为 | 适用场景 |
|----------|-----------|---------|
| OBS 默认域名 (`*.obs-website.*`) | 强制下载 | curl 调试、API 调用 |
| 自定义域名 (`chat.resource-governance.cloud`) | 正常渲染 | 生产访问 |

---

## 2. 架构

```
用户浏览器
    │
    ▼
chat.resource-governance.cloud  (CNAME)
    │
    ▼
personal-assistant-web-chat.obs-website.cn-southwest-2.myhuaweicloud.com  (OBS 静态网站)
    │
    ▼
index.html → React SPA → /assets/*.js, /assets/*.css
```

- **DNS**：华为云 DNS，CNAME 记录指向 OBS website endpoint
- **OBS**：`personal-assistant-web-chat` bucket，ACL `public-read`，SPA 回退（`error_document = index.html`）
- **Infra**：OpenTofu + HCL（`personal-assistant-infra/`）

---

## 3. 设置步骤

### 3.1 Infrastructure（OpenTofu）

**文件**：`personal-assistant-infra/dns.tf`

```hcl
# 引用华为云购买域名时自动创建的 Zone
resource "huaweicloud_dns_zone" "main" {
  name        = "resource-governance.cloud"
  description = "Personal Assistant 主域名"
  zone_type   = "public"
}

# CNAME: chat → OBS website endpoint
resource "huaweicloud_dns_recordset" "chat" {
  zone_id     = huaweicloud_dns_zone.main.id
  name        = "chat.resource-governance.cloud."
  type        = "CNAME"
  ttl         = 300
  records     = ["${huaweicloud_obs_bucket.web_chat.bucket}.obs-website.${var.region}.myhuaweicloud.com."]
  description = "Web Chat 前端入口 → OBS 静态网站"
}
```

**部署**：

```bash
cd personal-assistant-infra
tofu import huaweicloud_dns_zone.main <zone-id>   # 首次：导入已有 Zone
tofu apply                                         # 创建 CNAME 记录
```

> Zone ID 从华为云 DNS 控制台或首次 `tofu apply` 报错信息中获取。

### 3.2 OBS 控制台（手动 — Terraform 不支持此资源）

1. 登录 [华为云 OBS 控制台](https://console.huaweicloud.com/console/#/obs)
2. 进入 bucket → `personal-assistant-web-chat`
3. 左侧菜单 → **域名管理** → 点击 **绑定用户域名**
4. 输入：`chat.resource-governance.cloud`
5. 确认

> 华为云 Terraform Provider（`huaweicloud/huaweicloud` v1.92）不支持 `huaweicloud_obs_bucket_custom_domain` 资源，此步骤无法 IaC 化。

### 3.3 等待 DNS 生效

CNAME 记录 TTL 为 300 秒，通常 5-10 分钟全球生效。

```bash
# 验证 DNS 解析
dig chat.resource-governance.cloud CNAME

# 验证 OBS 响应
curl -sI http://chat.resource-governance.cloud/index.html | grep -i content-type
# 期望：Content-Type: text/html（非 application/octet-stream）
```

---

## 4. Historical：OBS 前端部署（GitHub Actions）

旧 OBS workflow 已删除。当前 workflow 为
`.github/workflows/deploy-frontend-to-cloudflare.yml`，详见
[`cloudflare/pages.md`](./cloudflare/pages.md)。

部署流程：

```
git push main
  → npm ci + tsc + vite build（VITE_API_BASE_URL 嵌入）
  → aws s3 sync dist/ s3://personal-assistant-web-chat/ --delete --acl public-read
  → Smoke test: curl http://chat.resource-governance.cloud
```

### 4.1 上传工具选型经验

| 工具 | 结果 | 问题 |
|------|------|------|
| **obsutil** | ❌ 放弃 | 下载困难（OBS 社区桶 AccessDenied）、目录处理怪异（`dist/` 被当成对象前缀上传）、需手动设 Content-Type、清理残留文件需额外 `rm` 命令 |
| **aws s3** | ✅ 采用 | ubuntu runner 自带，`sync --delete` 一行搞定，自动推断 MIME，但需要额外处理三个兼容问题（见 §5） |

### 4.2 `aws s3` 与 OBS 兼容性配置

AWS CLI v2（ubuntu-latest 自带 v2.23+）与华为云 OBS S3 API 的兼容性需要三项配置：

```yaml
env:
  AWS_REQUEST_CHECKSUM_CALCULATION: when_required    # AWS CLI v2.23+ 新 checksum → OBS 不兼容
  AWS_RESPONSE_CHECKSUM_VALIDATION: when_required    # 同上
run: |
  aws configure set s3.addressing_style virtual      # OBS 要求 virtual-host 风格
  aws s3 sync dist/ s3://bucket/ --endpoint-url=https://obs.cn-southwest-2.myhuaweicloud.com ...
```

---

## 5. 踩坑记录

### 5.1 OBS 默认域名强制下载

**现象**：浏览器访问 `https://personal-assistant-web-chat.obs-website.cn-southwest-2.myhuaweicloud.com` 直接下载 `index.html` 文件。

**排查**：curl 不带 `User-Agent` 不触发，`Content-Type` 正常为 `text/html`。浏览器带完整 UA → OBS 注入 `Content-Disposition: attachment`。

**解决**：绑定自定义域名（§3.2）。

### 5.2 AWS CLI `XAmzContentSHA256Mismatch`

**现象**：`aws s3 sync` 上传时所有文件报 `XAmzContentSHA256Mismatch`。

**根因**：AWS CLI v2.23.0+ 引入了新的 payload checksum 算法（CRC64NVME + trailing checksum trailers），OBS S3 API 不兼容。

**解决**：设 `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` 和 `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required`。

> 尝试过但无效的方案：`s3.payload_signing_enabled=false`、`s3.signature_version=s3`（SigV2）。

### 5.3 AWS CLI `VirtualHostDomainRequired`

**现象**：`aws s3 sync` 报 `VirtualHostDomainRequired`。

**根因**：OBS 要求 virtual-host 风格地址（`bucket.obs.cn-southwest-2...`），AWS CLI 默认 path 风格（`obs.cn-southwest-2.../bucket`）。

**解决**：`aws configure set s3.addressing_style virtual`。

### 5.4 obsutil 目录处理

**现象**：`obsutil cp dist/ obs://bucket/ -r` 将 `dist/` 作为对象前缀上传（文件变成 `dist/index.html` 而非 `index.html`）。

**解决**：如果使用 obsutil，需显式指定每个文件路径：`obsutil cp dist/index.html obs://bucket/index.html`（但最终改用 `aws s3` 避免了此问题）。

### 5.5 OBS 对象 ACL 默认私有

**现象**：Bucket 设了 `public-read`，但 `obsutil cp` 上传的对象为私有，OBS website endpoint 返回 404。

**解决**：上传时加 `-acl=public-read`（obsutil）或 `--acl public-read`（aws s3）。

### 5.6 Terraform Provider 资源缺失

`huaweicloud/huaweicloud` provider v1.92 不支持：
- `resource "huaweicloud_obs_bucket_custom_domain"` — OBS 域名绑定，需控制台手动
- `data "huaweicloud_dns_zone"` — DNS Zone 数据源，需用 `resource` + `tofu import`

### 5.7 DNS Zone 已存在 — 为什么需要 `tofu import`

在华为云购买的域名会自动创建 DNS Zone。当 OpenTofu 配置中声明了同名 Zone 资源时：

```bash
tofu apply
# → Error: DNS.0208: This zone already exists
```

直接 `apply` 会失败，因为 OpenTofu 试图**创建**一个已存在的资源。

**`tofu import` 的作用**：将云端已有资源"注册"到 OpenTofu 的 state 文件中，让 OpenTofu 接管管理权，而不是重新创建。

```bash
tofu import huaweicloud_dns_zone.main <zone-id>
```

导入后，`tofu apply` 只会执行**差异部分**（本例中只有新增的 CNAME 记录），不会尝试重复创建 Zone。

> 类比：`git clone` 已有仓库 vs `git init` 新仓库。`import` = clone 现有资源，`apply` = init + commit。

---

## 6. 当前状态

| 资源 | 状态 | 备注 |
|------|------|------|
| OBS Bucket | ✅ | `personal-assistant-web-chat`，ACL public-read，website hosting 已配 |
| DNS Zone | ✅ | `resource-governance.cloud`，已 import 到 OpenTofu state |
| CNAME 记录 | ✅ | `chat` → OBS website endpoint |
| OBS 域名绑定 | ⏳ | 需在 OBS 控制台手动绑定 `chat.resource-governance.cloud` |
| 前端文件 | ✅ | 通过 GitHub Actions 自动部署到 OBS |
| 浏览器渲染 | ⏳ | 域名绑定完成后即正常 |

---

## 7. 后续改进

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P0 | **ICP 备案** | 域名未备案可能被阻断。如果访问不通，需先完成 ICP 备案 |
| P1 | **CDN + HTTPS** | 目前自定义域名只支持 HTTP。加 CDN 后获得 HTTPS + 缓存加速 + Header 改写能力 |
| P2 | **CDN 路径回源** | CDN 配置 `/api/*` → AgentArts Runtime、`/*` → OBS。前后端同域，消除 CORS |
| P3 | **OBS Terraform 资源补齐** | 等 provider 支持 `huaweicloud_obs_bucket_custom_domain` 后纳入 IaC |
