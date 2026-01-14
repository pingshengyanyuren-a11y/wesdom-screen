我将通过以下五个步骤，将您现有的智能体升级为具备全功能 RAG、多轮对话记忆和流式响应的专业助手：

### 第一步：构建向量知识库 (Vector RAG)
目前系统仅使用数据库统计信息作为上下文（Context Injection）。为了实现“全面理解项目文档和代码库”，我将引入向量检索技术。
- **引入技术栈**：使用 `chromadb` (轻量级向量库) 和 `sentence-transformers` (本地 Embedding 模型) 或 SiliconFlow Embedding API。
- **文档处理**：创建 `knowledge_base` 目录，编写脚本扫描项目源码 (`.py`, `.js`, `.vue`) 和文档 (`.md`)，将其切片并向量化。
- **混合检索**：保留现有的 `generate_rag_context` (结构化实时数据)，并结合新的向量检索 (非结构化文档知识)，构建更完整的 Prompt。

### 第二步：实现多轮对话记忆 (Contextual Memory)
目前的 `ask_agent` 是无状态的。我将为其添加短期记忆功能。
- **会话管理**：在后端实现基于 `session_id` 的会话管理器 (In-Memory 存储，可扩展为 Redis)。
- **历史回溯**：在调用 Qwen 模型时，自动携带最近 10 轮对话历史，确保智能体能理解“它”、“上面提到的那个问题”等指代词。

### 第三步：性能极致优化 (Streaming Response)
为了达成“500ms 首字响应”的目标，必须从“等待完整生成”改为“流式输出”。
- **流式改造**：重构 `ai_analyzer.py` 的调用逻辑，开启 `stream=True`。
- **接口升级**：将 `/api/ask_agent` 改造为 Server-Sent Events (SSE) 接口，让前端能实时逐字显示回答，极大幅度降低用户感知的延迟。

### 第四步：安全与权限控制
- **API 鉴权**：添加 `@require_api_key` 装饰器，确保只有授权的客户端（或带有正确 Token 的请求）才能调用智能体接口。
- **环境隔离**：将 API Key 等敏感信息移至环境变量或独立的配置文件中，避免硬编码。

### 第五步：测试与验证体系
- **自动化测试**：编写 `test_agent_capabilities.py`，包含：
    - **知识检索测试**：提问项目具体代码实现，验证是否能检索到正确文件。
    - **多轮对话测试**：进行连续追问，验证记忆能力。
    - **延迟测试**：计算 Time to First Token (TTFT)，确保满足 500ms 要求。

**准备工作**：
我将首先检查并安装必要的依赖库 (`chromadb`, `sentence_transformers` 等)，然后按顺序执行上述计划。
