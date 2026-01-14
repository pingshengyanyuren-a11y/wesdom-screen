---
description: 智慧水利监测平台项目规范和约定
---

# 🛡️ Global Project Rules (项目全局规范)

为了确保系统的稳定性和代码质量，本项目严格执行以下开发流程。

## 1. 强制计划先行 (Mandatory Planning Protocol)
**规则：** 对于任何"比较复杂"的执行任务（Complex Execution），必须**先制定计划，经用户确认后方可执行**。

**"复杂任务"定义：**
- 修改涉及多个文件。
- 修改涉及后端核心逻辑（如 API、算法流程）。
- 修改涉及架构调整（如引入新库、改变数据流）。
- 涉及不可逆的操作（如删除关键数据、重置数据库）。

**执行流程：**
1.  **[PLANNING] 阶段**：
    - 分析需求。
    - 在 `implementation_plan.md` 中详细列出：
        - **核心问题** (Problem Analysis)
        - **拟定方案** (Proposed Solution)
        - **修改文件列表** (Implementation Details)
        - **风险评估** (Risk Assessment)
    - 使用 `notify_user` 提交计划，并明确询问："请审批此计划"。
2.  **[WAITING] 阶段**：
    - 等待用户回复 "同意"、"通过" 或 "Proceed"。
    - **严禁**在此阶段提前修改代码。
3.  **[EXECUTION] 阶段**：
    - 获得批准后，方可进入执行模式。
    - 严格按照计划步骤执行。
4.  **[VERIFICATION] 阶段**：
    - 执行完成后进行验证，并报告结果。

## 2. 端口与服务约定
- **Frontend**: Port `10086`
- **Backend**: Port `5001`
- **启动方式**: 必须使用 `一键启动全部服务.bat` 或其对应的清理逻辑，防止僵尸进程。

## 3. 语言规范
- 全程使用 **Simplified Chinese (简体中文)** 进行沟通和注释。
