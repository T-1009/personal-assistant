# DevOps — Microsoft Entra ID (OIDC) 配置指南

> 版本：v1.0 | 状态：Active | 关联文档：[`overall_architecture.md`](../overall_architecture.md), [`local-development.md`](local-development.md)

---

本指南详细说明了如何配置 **Microsoft Entra ID (原 Azure Active Directory)** 作为 Personal Assistant 的 Inbound/Outbound OIDC Identity Provider。

## 1. 门户入口

Microsoft 提供的 OAuth 2.0 / OIDC 应用注册界面统一收拢在 **Microsoft Entra** 体系中。开发人员可通过以下两个门户进行管理：

*   **官方推荐：Microsoft Entra 管理中心 (Entra Admin Center)**
    *   **访问地址**：[https://entra.microsoft.com/](https://entra.microsoft.com/)
    *   **登录账户**：使用您的 Microsoft 企业/学校账户或个人账户登录。
*   **备选入口：Azure Portal (传统 Azure 门户)**
    *   **访问地址**：[https://portal.azure.com/](https://portal.azure.com/)

---

## 2. 应用注册步骤 (App Registration)

### 2.1 路径导航
1. 登录 **Microsoft Entra 管理中心**。
2. 在左侧菜单栏中展开 **Identity**（标识）分类。
3. 点击 **Applications**（应用程序）-> **App registrations**（应用注册）。
4. 点击顶部菜单栏的 **New registration**（新注册）按钮。

### 2.2 基础信息配置
进入注册表单后，按以下参数配置：

*   **Name (名称)**: `personal-assistant-dev` (或根据部署环境命名)
*   **Supported account types (支持的账户类型)**:
    *   选择第三项：`Accounts in any organizational directory and personal Microsoft accounts`（即 **多租户 + 个人 Microsoft 账户**），允许任何人使用其微软个人/企业账号登录该 Agent。
*   **Redirect URI (重定向 URI)**:
    *   下拉框平台选择：**Web**（对应后端 FastAPI 处理 OIDC 回调流）。
    *   URL 填写：本地开发填 `http://localhost:8080/auth/callback`，生产部署填后端实际网关或代理的回调地址。
*   点击底部的 **Register**（注册）按钮完成创建。

---

## 3. 密钥与权限配置

注册完成后，进入该应用的详情页面。

### 3.1 客户端密码 (Client Secret)
对于后端的 Authorization Code Flow，需要生成密钥用于向 Microsoft 换取 `id_token`/`access_token`：
1. 点击左侧导航栏的 **Certificates & secrets**（证书和密码）。
2. 在 **Client secrets** 页签下，点击 **New client secret**（新建客户端密码）。
3. 填写 **Description**（例如 `pa-backend-dev-secret`）及 **Expires**（有效期建议选择 180 天），点击 **Add**。
4. **【强制安全要求】**：创建成功后，请立即复制其 **Value (值)** 并保存。离开此页面后该值将被永久隐藏，若丢失需重新生成。

### 3.2 API 权限 (API Permissions)
确保 OIDC 流程能正常获取用户标识和基础属性（如邮箱）：
1. 点击左侧导航栏的 **API permissions**（API 权限）。
2. 确保已默认添加 **Microsoft Graph** -> **User.Read** 权限。
3. 如果尚未添加，点击 **Add a permission** -> 选择 **Microsoft Graph** -> **Delegated permissions**，搜索并勾选 `openid`, `profile`, `email` 权限并保存。

---

## 4. 关键环境变量与 OIDC 端点

配置完成后，请从 **Overview (概述)** 页面中提取以下核心配置并写入项目 `.env` 配置文件：

### 4.1 核心配置字段对照表

| 配置项 | 平台显示名称 | 说明 | 示例值 |
|--------|--------------|------|--------|
| `MICROSOFT_CLIENT_ID` | Application (client) ID | 标识此应用的唯一 ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `MICROSOFT_CLIENT_SECRET` | Secret Value | Step 3.1 生成的客户端密码 | `_xx~xxxxxxxxxxxxxxxxxxxxxxxxx` |
| `MICROSOFT_TENANT_ID` | Directory (tenant) ID | 多租户架构下可直接填写 `common` | `common` |

### 4.2 OIDC Discovery 端点
本系统通过 Microsoft 标准 OIDC 元数据发现端点获取公钥集和验证 URL：

```http
https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration
```

> **网络说明**：`login.microsoftonline.com` 在国内网络（包括华为内网）无任何 GFW 阻断，请求解析极为稳定。

---

## 5. 本地开发集成验证

1. 确保在后端 `personal-assistant-service/.env` 中正确配置了上述环境变量。
2. 运行 `uvicorn app.main:app --port 8080 --reload` 启动本地后端。
3. 引导用户访问前端 Web Chat，点击 **Sign in with Microsoft**。
4. 浏览器重定向至 Microsoft 登录页面，登录成功后，微软会将 `code` 返回至回调端点 `http://localhost:8080/auth/callback`，后端校验无误后颁发 JWT，建立安全 Session。
