"""
零代碼工具自動吸納器 (Zero-Code Tool Loader: OpenAPI 3.0 & FastMCP Ingestion)
支援從標準 OpenAPI / Swagger 3.0 規格或 Model Context Protocol (MCP) 規格中，
自動將遠端端點或宣告轉換為受 AST 與安全護欄保護的 BaseTool 實例。
"""

import json
from typing import Any, Callable, Dict, List, Optional, Union
from ..types import RiskLevel
from .base_tool import BaseTool


class DynamicOpenAPITool(BaseTool):
    """由 OpenAPI 規格動態生成的標準工具"""

    def __init__(
        self,
        name: str,
        description: str,
        path: str,
        method: str,
        parameters_schema: Dict[str, Any],
        risk_level: RiskLevel = RiskLevel.LOW,
        executor_func: Optional[Callable[..., Any]] = None,
    ):
        self.name = name
        self.description = description
        self.risk_level = risk_level.value if hasattr(risk_level, "value") else str(risk_level)
        self.path = path
        self.method = method.upper()
        self.parameters_schema = parameters_schema
        self._executor_func = executor_func

    def execute(self, **kwargs) -> Any:
        if self._executor_func:
            return self._executor_func(self.path, self.method, kwargs)
        # 預設模擬調用執行
        return {
            "status": "success",
            "endpoint": f"{self.method} {self.path}",
            "passed_arguments": kwargs,
            "mock_response": f"Successfully routed to {self.path} with parameters {list(kwargs.keys())}",
        }


class DynamicMCPTool(BaseTool):
    """由 FastMCP / MCP 協定規格動態生成的標準工具"""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        risk_level: RiskLevel = RiskLevel.LOW,
        caller_func: Optional[Callable[..., Any]] = None,
    ):
        self.name = name
        self.description = description
        self.risk_level = risk_level.value if hasattr(risk_level, "value") else str(risk_level)
        self.input_schema = input_schema
        self._caller_func = caller_func

    def execute(self, **kwargs) -> Any:
        if self._caller_func:
            return self._caller_func(self.name, kwargs)
        return {
            "status": "success",
            "mcp_tool": self.name,
            "arguments": kwargs,
            "result": f"Executed MCP capability [{self.name}] safely via AdaptiveRouter.",
        }


class ToolLoader:
    """工具加載與規格自動適配器工廠"""

    @staticmethod
    def infer_risk_level(method: str, path_or_name: str, description: str = "") -> RiskLevel:
        """依據 HTTP Method 與語意關鍵字自動推論風險等級"""
        text = f"{method} {path_or_name} {description}".lower()
        if any(w in text for w in ["drop", "delete", "destroy", "truncate", "purge", "pay", "order_execute"]):
            return RiskLevel.CRITICAL
        if any(w in text for w in ["update", "modify", "alter", "create", "insert", "post", "put", "patch"]):
            return RiskLevel.HIGH
        if any(w in text for w in ["batch", "crawl", "export_large"]):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @classmethod
    def from_openapi_spec(
        cls,
        spec: Union[str, Dict[str, Any]],
        executor: Optional[Callable[[str, str, Dict[str, Any]], Any]] = None,
    ) -> List[BaseTool]:
        """從 OpenAPI 3.0 / Swagger 規格自動生成 Tools"""
        if isinstance(spec, str):
            spec_dict = json.loads(spec)
        else:
            spec_dict = spec

        tools: List[BaseTool] = []
        paths = spec_dict.get("paths", {})

        for path, methods in paths.items():
            for method, op_data in methods.items():
                if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                    continue

                op_id = op_data.get("operationId") or f"{method.lower()}_{path.replace('/', '_').strip('_')}"
                summary = op_data.get("summary") or op_data.get("description") or f"Call {method.upper()} {path}"
                risk = cls.infer_risk_level(method, path, summary)

                # 提取參數規格
                param_schema = {
                    "parameters": op_data.get("parameters", []),
                    "requestBody": op_data.get("requestBody", {}),
                }

                tool = DynamicOpenAPITool(
                    name=op_id,
                    description=summary,
                    path=path,
                    method=method,
                    parameters_schema=param_schema,
                    risk_level=risk,
                    executor_func=executor,
                )
                tools.append(tool)

        return tools

    @classmethod
    def from_mcp_spec(
        cls,
        tools_list: List[Dict[str, Any]],
        caller: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ) -> List[BaseTool]:
        """從 FastMCP / Model Context Protocol 宣告自動生成 Tools"""
        tools: List[BaseTool] = []
        for item in tools_list:
            name = item.get("name", "unknown_tool")
            description = item.get("description", "")
            input_schema = item.get("inputSchema", {})
            risk = cls.infer_risk_level("CALL", name, description)

            tool = DynamicMCPTool(
                name=name,
                description=description,
                input_schema=input_schema,
                risk_level=risk,
                caller_func=caller,
            )
            tools.append(tool)
        return tools
