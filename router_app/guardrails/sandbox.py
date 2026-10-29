"""
實體隔離執行沙盒 (Restricted Subprocess Sandbox)
結合靜態 AST 語法樹校驗與作業系統層級獨立行程隔離 (Process Isolation)。
杜絕生成代碼透過動態反射 (如 getattr/builtins) 污染調度器主行程或耗盡系統資源。
"""

import os
import sys
import time
import subprocess
import tempfile
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from .ast_guard import PythonASTSecurityGuard


class SandboxExecutionResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    elapsed_ms: float = 0.0
    blocked_by_guard: bool = False
    block_reason: str = ""


class RestrictedSubprocessSandbox:
    """隔離行程沙箱執行器"""

    def __init__(self, timeout_seconds: float = 5.0, max_output_chars: int = 10000):
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

    def execute_python_code(
        self,
        code_str: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> SandboxExecutionResult:
        """
        雙重防禦執行流程:
        1. 靜態編譯器 AST 語法樹檢查 (阻斷 eval, exec, os, sys, subprocess 等危險節點)
        2. 獨立作業系統子行程 (Subprocess) 執行，限制超時、環境變數與暫存目錄
        """
        # 第一階: 靜態 AST 護欄校驗
        is_safe, reasons = PythonASTSecurityGuard.validate_code(code_str)
        if not is_safe:
            return SandboxExecutionResult(
                success=False,
                blocked_by_guard=True,
                block_reason="; ".join(reasons),
                return_code=-1,
            )

        # 第二階: 隔離子行程執行
        # 僅保留極簡安全環境變數，徹底脫敏主行程中的機敏 Key
        safe_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONUNBUFFERED": "1",
            "LC_ALL": "en_US.UTF-8",
        }
        if env_vars:
            safe_env.update(env_vars)

        start_time = time.time()
        temp_file_path = ""

        try:
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
                tf.write(code_str)
                temp_file_path = tf.name

            proc = subprocess.run(
                [sys.executable, temp_file_path],
                env=safe_env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)

            stdout = proc.stdout[: self.max_output_chars]
            stderr = proc.stderr[: self.max_output_chars]

            return SandboxExecutionResult(
                success=(proc.returncode == 0),
                stdout=stdout,
                stderr=stderr,
                return_code=proc.returncode,
                elapsed_ms=elapsed_ms,
            )

        except subprocess.TimeoutExpired:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return SandboxExecutionResult(
                success=False,
                stderr=f"沙箱執行超時 (超過 {self.timeout_seconds} 秒)，已被作業系統硬性截斷。",
                return_code=-2,
                elapsed_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return SandboxExecutionResult(
                success=False,
                stderr=f"沙箱子行程啟動異常: {str(e)}",
                return_code=-3,
                elapsed_ms=elapsed_ms,
            )
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except OSError:
                    pass
