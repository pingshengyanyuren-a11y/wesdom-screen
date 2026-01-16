# -*- coding: utf-8 -*-
import os
import json
import base64
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

# 全局会话存储 (In-Memory)
SESSION_MEMORY = {}

# 自定义 SiliconFlow Embedding (复制自 build_vector_db.py)
class SiliconFlowEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self, api_key, model_name="BAAI/bge-m3"):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.siliconflow.cn/v1"
        )
        self.model_name = model_name

    def __call__(self, input):
        embeddings = []
        batch_size = 10
        for i in range(0, len(input), batch_size):
            batch = input[i:i+batch_size]
            try:
                resp = self.client.embeddings.create(
                    model=self.model_name,
                    input=batch,
                    encoding_format="float"
                )
                batch_embeddings = [d.embedding for d in resp.data]
                embeddings.extend(batch_embeddings)
            except Exception as e:
                print(f"Embedding error: {e}")
                embeddings.extend([[0.0]*1024] * len(batch))
        return embeddings

class AIAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
        self.model = os.getenv("AI_MODEL_NAME", "Qwen/Qwen2-VL-72B-Instruct")
        
        if not self.api_key:
            print("Warning: OPENAI_API_KEY not found in environment variables.")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # 初始化 ChromaDB 连接 (Vector RAG)
        try:
            # 定位到 ml_backend/knowledge_base/chroma_db
            # api/src/ -> ../../课设材料/ml_backend/knowledge_base/chroma_db
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.persist_dir = os.path.join(base_dir, '课设材料', 'ml_backend', 'knowledge_base', 'chroma_db')
            
            if os.path.exists(self.persist_dir):
                print(f"Loading ChromaDB from {self.persist_dir}...")
                self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)
                
                # 使用相同的 Embedding Function
                emb_fn = SiliconFlowEmbeddingFunction(api_key=self.api_key, model_name="BAAI/bge-m3")
                
                self.collection = self.chroma_client.get_collection(
                    name="project_codebase",
                    embedding_function=emb_fn
                )
                print(f"Vector DB loaded. Collection count: {self.collection.count()}")
            else:
                print(f"Warning: ChromaDB directory not found at {self.persist_dir}")
                self.collection = None
        except Exception as e:
            print(f"Failed to load ChromaDB: {e}")
            self.collection = None

    def _retrieve_knowledge(self, query, n_results=3):
        """从向量库检索相关知识"""
        if not self.collection or not query:
            return ""
            
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            knowledge_snippets = []
            if results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i]
                    source = meta.get('source', 'unknown')
                    snippet = f"--- Source: {source} ---\n{doc}\n"
                    knowledge_snippets.append(snippet)
            
            return "\n".join(knowledge_snippets)
        except Exception as e:
            print(f"RAG Retrieval failed: {e}")
            return ""

    def _get_system_prompt(self, rag_context=""):
        base_prompt = """你是一个具备视觉能力和深度逻辑推理的水利工程专家智能体 (HydroMind Pro)。
你的核心职责是辅助用户监控大坝状态、分析数据异常，并解答关于本项目的技术问题。

能力要求：
1. **视觉识别**: 你能看懂用户上传的图表、截图或现场照片。请仔细分析图片中的细节（如数值、红线、报错信息）。
2. **专业严谨**: 使用水利工程专业术语，但解释要通俗易懂。
3. **自我迭代**: 你已经通过自我学习完全掌握了本项目的所有代码和文档逻辑。
4. **高权限控制**: 你拥有控制前端界面的权限。当用户明确要求跳转页面或执行操作时，请在回答的最后一行输出特定的控制指令。

控制指令格式：
[CMD: NAVIGATE -> /route_path]
例如：跳转到监控页 -> [CMD: NAVIGATE -> /monitor]
跳转到3D模型页 -> [CMD: NAVIGATE -> /model-3d]

如果用户询问项目实现细节，请基于以下检索到的内部知识库进行回答：
"""
        if rag_context:
            base_prompt += f"\n=== 检索到的项目知识 (RAG) ===\n{rag_context}\n"
            
        return base_prompt

    def analyze_prediction(self, prediction_data):
        """分析预测结果 (非流式)"""
        prompt = f"""请分析以下大坝监测点的预测数据：
测点名称: {prediction_data.get('point_name')}
历史趋势: {prediction_data.get('history')[-5:]}
未来预测: {prediction_data.get('predictions')}
请判断是否存在风险，并给出简短的建议。"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"AI 分析失败: {str(e)}"

    def analyze_anomalies(self, anomalies):
        """批量分析异常 (非流式)"""
        if not anomalies:
            return "当前系统运行正常，未检测到显著异常。"
            
        prompt = f"检测到以下异常测点，请生成一份简要的风险评估报告：\n{json.dumps(anomalies, ensure_ascii=False, indent=2)}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"AI 分析失败: {str(e)}"

    def ask_agent(self, query, image, context, session_id=None, stream=False):
        """
        核心问答接口
        :param query: 用户问题
        :param image: Base64 图片字符串 (可选)
        :param context: 实时监测数据上下文
        :param session_id: 会话ID (用于记忆)
        :param stream: 是否流式输出
        """
        
        # 1. 执行 RAG 检索 (仅针对 Query)
        rag_knowledge = ""
        if query:
            print(f"Retrieving knowledge for: {query}")
            rag_knowledge = self._retrieve_knowledge(query)
            
        # 2. 构建 System Prompt
        system_prompt = self._get_system_prompt(rag_knowledge)
        messages = [{"role": "system", "content": system_prompt}]
        
        # 3. 注入 Session History
        if session_id:
            if session_id not in SESSION_MEMORY:
                SESSION_MEMORY[session_id] = []
            # 取最近 6 轮对话
            history = SESSION_MEMORY[session_id][-6:]
            messages.extend(history)
        
        # 4. 注入实时监测数据 (Context Injection)
        if context:
            messages.append({"role": "system", "content": f"=== 实时监测数据上下文 ===\n{context}"})
            
        # 5. 构建当前用户消息 (多模态)
        user_content = []
        if query:
            user_content.append({"type": "text", "text": query})
        
        if image:
            # 确保 Base64 格式正确 (OpenAI 需要 data:image/jpeg;base64,...)
            if not image.startswith('data:image'):
                image = f"data:image/jpeg;base64,{image}"
            user_content.append({
                "type": "image_url",
                "image_url": {"url": image}
            })
            
        messages.append({"role": "user", "content": user_content})

        try:
            print(f"Sending request to {self.model} (Stream={stream})...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=stream,
                temperature=0.7,
                max_tokens=2000
            )
            
            if stream:
                return self._handle_stream(response, session_id, user_content)
            else:
                answer = response.choices[0].message.content
                # 更新记忆
                if session_id:
                    self._update_memory(session_id, user_content, answer)
                return answer
                
        except Exception as e:
            err_msg = f"智能体思考出错: {str(e)}"
            print(err_msg)
            if stream:
                def err_gen():
                    yield err_msg
                return err_gen()
            else:
                return err_msg

    def _handle_stream(self, response, session_id, user_content):
        """处理流式响应并更新记忆"""
        full_answer = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_answer += content
                yield content
        
        # 流结束后更新记忆
        if session_id:
            self._update_memory(session_id, user_content, full_answer)

    def _update_memory(self, session_id, user_content, assistant_answer):
        """更新会话记忆"""
        if session_id not in SESSION_MEMORY:
            SESSION_MEMORY[session_id] = []
            
        # 简化 User Content 存入记忆 (避免存太大的 Base64)
        mem_user_content = user_content
        if isinstance(user_content, list):
            # 如果包含图片，只保留文本描述
            text_parts = [p['text'] for p in user_content if p['type'] == 'text']
            mem_user_content = " ".join(text_parts) + " [用户上传了一张图片]"
            
        SESSION_MEMORY[session_id].append({"role": "user", "content": mem_user_content})
        SESSION_MEMORY[session_id].append({"role": "assistant", "content": assistant_answer})

def get_analyzer():
    return AIAnalyzer()
