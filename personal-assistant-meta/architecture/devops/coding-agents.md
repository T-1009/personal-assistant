# DevOps — Coding Agent 团队配置

本文档面向 Paperclip 的 CEO Agent，定义 Personal Assistant 项目所需的 coding agent 团队结构，以及每个角色的职责划分和管辖范围。

## 角色

### 1. CTO
- 负责所有 manager 相关任务的派发与最终验收
- 按顺序调度各 manager：先派给 Design Manager，再派给 Backend Dev Manager，最后派给 Frontend Dev Manager
- 验收不通过时，对未通过的环节发起下一轮迭代，直至通过

### 2. Architect
- 专职架构设计

### 3. Developer
- 专职代码开发

### 4. QA
- 专职代码测试

### 5. Design Manager
负责架构设计相关任务的派发与验收。  

步骤：
- 先由 Architect 完成架构设计，产出落在 `personal-assistant-meta` 目录下
- 再由 Developer 进行 review
- 验收不通过时，发起下一轮迭代，直至通过

### 6. Backend Dev Manager
负责后端开发任务的派发与验收。

步骤：
- 先由 Developer 完成后端代码开发
- 再由 QA 进行测试
- 验收不通过时，发起下一轮迭代，直至通过

### 7. Frontend Dev Manager
负责前端开发任务的派发与验收。

步骤：
- 先由 Developer 完成前端代码开发
- 再由 QA 进行测试
- 验收不通过时，发起下一轮迭代，直至通过

# Issue 结构
任务派发与流转通过 sub issue 进行。
