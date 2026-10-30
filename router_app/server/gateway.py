"""
企業級 OpenAI 相容反向代理閘道伺服器 (Zero-Code OpenAI-Compatible Gateway)
純 Python 標準庫實作 (基於 ThreadingHTTPServer)，零重量外部依賴，支援並發連線。
提供標準 /v1/chat/completions (含 SSE 串流)、/v1/models、/metrics 與 /healthz。
讓任何前端 (Open WebUI, Dify, Cursor, LangChain) 只需更改 OPENAI_BASE_URL 即可直接接入！
"""

import json
import time
import uuid
import argparse
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional
from ..dispatcher import AdaptiveAgentDispatcher
from ..types import AgentMode, StreamEventType
from ..tracing.metrics import metrics


class OpenAIGatewayHandler(BaseHTTPRequestHandler):
    """處理標準 OpenAI 與 Prometheus 請求的 HTTP 處理器"""

    dispatcher: AdaptiveAgentDispatcher = None

    def address_string(self):
        """防止 macOS 預設逆向 DNS 查找 (Reverse DNS Lookup) 造成 5~10 秒連線超時"""
        return str(self.client_address[0])

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        """跨域資源共用 (CORS) 預檢支援"""
        self._set_headers(200)

    def do_GET(self):
        """處理 GET 端點: /healthz, /metrics, /v1/models"""
        if self.path == "/healthz" or self.path == "/":
            self._set_headers(200)
            payload = {
                "status": "healthy",
                "service": "adaptive-agent-router-gateway",
                "version": "1.0.0",
                "uptime": time.time(),
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        elif self.path == "/metrics":
            self._set_headers(200, content_type="text/plain; version=0.0.4; charset=utf-8")
            prom_text = metrics.export_prometheus_text()
            self.wfile.write(prom_text.encode("utf-8"))
            return

        elif self.path == "/v1/models":
            self._set_headers(200)
            models_list = [
                {"id": "adaptive-router", "object": "model", "owned_by": "adaptive-agent-router"},
                {"id": "mode_1_single_turn", "object": "model", "owned_by": "adaptive-agent-router"},
                {"id": "mode_2_react", "object": "model", "owned_by": "adaptive-agent-router"},
                {"id": "mode_4_planner", "object": "model", "owned_by": "adaptive-agent-router"},
                {"id": "mode_5_reflection", "object": "model", "owned_by": "adaptive-agent-router"},
                {"id": "mode_6_verifier_gated", "object": "model", "owned_by": "adaptive-agent-router"},
                {"id": "mode_7_multi_agent", "object": "model", "owned_by": "adaptive-agent-router"},
                {"id": "mode_8_tool_use", "object": "model", "owned_by": "adaptive-agent-router"},
                {"id": "mode_9_ensemble", "object": "model", "owned_by": "adaptive-agent-router"},
                {"id": "mode_10_memory", "object": "model", "owned_by": "adaptive-agent-router"},
            ]
            self.wfile.write(json.dumps({"object": "list", "data": models_list}).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": f"Path not found: {self.path}"}).encode("utf-8"))

    def do_POST(self):
        """處理 POST 端點: /v1/chat/completions 與 /v1/tasks/{task_id}/resume"""
        if self.path == "/v1/chat/completions":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)

            try:
                body = json.loads(post_data.decode("utf-8"))
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": f"Invalid JSON payload: {str(e)}"}).encode("utf-8"))
                return

            messages = body.get("messages", [])
            stream = body.get("stream", False)
            model_req = body.get("model", "adaptive-router")

            # 萃取最後一則使用者提問
            user_prompt = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_prompt = msg.get("content", "")
                    break

            if not user_prompt:
                user_prompt = messages[-1].get("content", "") if messages else "Hello"

            # 檢查是否有強制模式
            forced_mode = None
            if model_req in [m.value for m in AgentMode]:
                forced_mode = AgentMode(model_req)

            # 萃取身分與權限安全標頭 (OWASP LLM03 & LLM10)
            client_id = self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or str(self.client_address[0])
            user_roles_hdr = self.headers.get("X-User-Roles", "")
            user_roles = [r.strip() for r in user_roles_hdr.split(",") if r.strip()] if user_roles_hdr else body.get("user_roles")
            operator_id = self.headers.get("X-Operator-Id") or self.headers.get("X-User-Id") or body.get("operator_id") or "api_gateway"

            # 1. 處理串流 SSE 回應
            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
                created_ts = int(time.time())

                # 透過 dispatcher 執行並模擬 Token 串流
                result = self.dispatcher.process(
                    user_prompt,
                    forced_mode=forced_mode,
                    client_id=client_id,
                    user_roles=user_roles,
                    operator_id=operator_id,
                )
                words = result.output.split(" ")

                for w in words:
                    chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": result.mode_used.value,
                        "choices": [
                            {"index": 0, "delta": {"content": w + " "}, "finish_reason": None}
                        ],
                    }
                    line = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                    self.wfile.write(line.encode("utf-8"))
                    self.wfile.flush()

                # 結束信號
                stop_chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": result.mode_used.value,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                self.wfile.write(f"data: {json.dumps(stop_chunk)}\n\n".encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                self.close_connection = True
                return

            # 2. 處理標準非串流回應
            result = self.dispatcher.process(
                user_prompt,
                forced_mode=forced_mode,
                client_id=client_id,
                user_roles=user_roles,
                operator_id=operator_id,
            )
            tokens = result.total_tokens_used or 150

            response_payload = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": result.mode_used.value,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": result.output},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": max(10, tokens // 3),
                    "completion_tokens": max(10, tokens * 2 // 3),
                    "total_tokens": tokens,
                },
                "adaptive_metadata": {
                    "mode_used": result.mode_used.value,
                    "success": result.success,
                    "steps_count": len(result.execution_steps),
                    "rag": result.metadata.get("rag"),
                    "acceleration": result.metadata.get("acceleration"),
                    "harness": result.metadata.get("harness"),
                },
            }

            self._set_headers(200)
            self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode("utf-8"))
            return

        elif "/resume" in self.path:
            # 支援 REST 審批喚醒: POST /v1/tasks/{task_id}/resume
            parts = self.path.strip("/").split("/")
            if len(parts) >= 3 and parts[0] == "v1" and parts[1] == "tasks":
                task_id = parts[2]
                content_length = int(self.headers.get("Content-Length", 0))
                post_data = self.rfile.read(content_length)
                try:
                    body = json.loads(post_data.decode("utf-8")) if post_data else {}
                    approved = body.get("approved", True)
                    operator_id = self.headers.get("X-Operator-Id") or body.get("operator_id") or "security_officer"
                    reason = body.get("reason", "")
                except Exception:
                    approved = True
                    operator_id = "security_officer"
                    reason = ""

                res = self.dispatcher.resume_task(task_id, approved=approved, operator_id=operator_id, reason=reason)
                self._set_headers(200)
                self.wfile.write(json.dumps({"task_id": task_id, "output": res.output, "success": res.success}, ensure_ascii=False).encode("utf-8"))
                return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": f"Endpoint not found: {self.path}"}).encode("utf-8"))


def run_gateway_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    enable_logging: bool = True,
    dispatcher: Optional[AdaptiveAgentDispatcher] = None,
    enable_rag: bool = True,
    enable_acceleration: bool = True,
    enable_harness: bool = True,
):
    """啟動 OpenAI 相容反向代理網關伺服器"""
    if dispatcher is None:
        from ..rag import AdaptiveRAGAdapter, InMemoryVectorRetriever
        from ..acceleration import LLMAccelerationController
        from ..harness import AgentHarness

        retriever = InMemoryVectorRetriever()
        retriever.add_document("corp_01", "Acme Corporation SLA requires 99.95% annual availability with 5% monthly fee credit per downtime hour.")
        retriever.add_document("corp_02", "Acme Corporate Tax ID is 28459201, headquarters located at Cloud Innovation Park.")

        rag_adapter = AdaptiveRAGAdapter(retriever=retriever) if enable_rag else None
        acc_controller = LLMAccelerationController() if enable_acceleration else None
        harness = AgentHarness() if enable_harness else None

        dispatcher = AdaptiveAgentDispatcher(
            rag_adapter=rag_adapter,
            acceleration_controller=acc_controller,
            harness=harness,
            enable_logging=enable_logging,
        )

    OpenAIGatewayHandler.dispatcher = dispatcher

    server = ThreadingHTTPServer((host, port), OpenAIGatewayHandler)
    if enable_logging:
        print("=" * 70)
        print(f"🚀 AdaptiveAgentRouter OpenAI-Compatible Gateway is LIVE!")
        print(f"📡 Base URL:        http://{host}:{port}/v1")
        print(f"📊 Metrics URL:     http://{host}:{port}/metrics")
        print(f"💓 Health Probe:    http://{host}:{port}/healthz")
        print(f"📦 Models Endpoint: http://{host}:{port}/v1/models")
        print("=" * 70)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if enable_logging:
            print("\nShutting down Gateway Server gracefully...")
        server.server_close()
