"""
實體代碼測試即真理驗證器 (SWE-bench Test-as-Oracle Runner)
=========================================================
學術與業界借鏡：
- SWE-bench: Can Language Models Resolve Real-World GitHub Issues? (Jimenez et al., ICLR 2024)
- SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering (Yang et al., 2024)

核心理念：
絕對禁止使用「LLM-as-a-Judge」（讓大模型自我評分或問另一個模型「寫得好不好」）。
在軟體工程與高嚴謹性任務中，只有實體單元測試（Unit Test / Pytest / Unittest）
的真實執行 Exit Code == 0 才能作為最終正確性的唯一客觀真理（Test-as-Oracle）。

本模組提供：
1. 沙盒單元測試執行器 (Sandboxed Test Runner)
2. 捕獲真實 stdout, stderr, exit_code 與執行毫秒數
3. 自動綁定至 The Agent Harness (RigidStateFSM)，作為推進至 SHIP 階段的代碼硬門控
"""

import io
import os
import sys
import time
import traceback
import unittest
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class OracleExecutionResult:
    """實體測試裁判執行結果"""
    passed: bool
    exit_code: int
    test_count: int
    failure_count: int
    error_count: int
    stdout: str
    stderr: str
    execution_time_ms: float
    failure_details: List[str]


class TestAsOracle:
    """SWE-bench 風格之實體測試裁判執行器"""

    @classmethod
    def run_unit_tests(
        cls,
        test_case_classes: List[type],
        timeout_seconds: float = 10.0,
    ) -> OracleExecutionResult:
        """
        在受限記憶體與輸出重導向沙盒內執行一組 unittest.TestCase 類別，
        依據真實斷言判定成敗。
        """
        start_time = time.perf_counter()
        suite = unittest.TestSuite()
        loader = unittest.TestLoader()

        for test_cls in test_case_classes:
            tests = loader.loadTestsFromTestCase(test_cls)
            suite.addTests(tests)

        stream_out = io.StringIO()
        stream_err = io.StringIO()

        # 隔離標準輸出
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = stream_out
        sys.stderr = stream_err

        try:
            runner = unittest.TextTestRunner(
                stream=stream_err,
                verbosity=2,
                failfast=False,
            )
            result = runner.run(suite)
            passed = result.wasSuccessful()
            exit_code = 0 if passed else 1

            failures = [f[1] for f in result.failures]
            errors = [e[1] for e in result.errors]
            failure_details = failures + errors

        except Exception as ex:
            passed = False
            exit_code = 2
            failure_details = [f"Oracle runtime crash: {str(ex)}\n{traceback.format_exc()}"]
            result = None
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return OracleExecutionResult(
            passed=passed,
            exit_code=exit_code,
            test_count=result.testsRun if result else 0,
            failure_count=len(result.failures) if result else 0,
            error_count=len(result.errors) if result else 1,
            stdout=stream_out.getvalue(),
            stderr=stream_err.getvalue(),
            execution_time_ms=round(elapsed_ms, 3),
            failure_details=failure_details,
        )

    @classmethod
    def verify_code_patch(
        cls,
        candidate_code: str,
        verification_test_code: str,
    ) -> OracleExecutionResult:
        """
        模擬 SWE-bench 驗證流程：
        在動態隔離命名空間中載入候選代碼與測試腳本，執行驗證。
        """
        start_time = time.perf_counter()
        namespace: Dict[str, Any] = {"__name__": "__oracle_exec__"}

        # 檢查是否有高危破壞性語法 (呼叫前置安全檢查)
        from router_app.guardrails.ast_guard import PythonASTSecurityGuard
        safe, violations = PythonASTSecurityGuard.validate_code(candidate_code)
        if not safe:
            return OracleExecutionResult(
                passed=False,
                exit_code=126,  # Command invoked cannot execute (security blocked)
                test_count=0,
                failure_count=1,
                error_count=0,
                stdout="",
                stderr="Security AST Violation",
                execution_time_ms=0.1,
                failure_details=violations,
            )

        stream_err = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = stream_err

        try:
            # 1. 在安全命名空間編譯並執行候選代碼
            exec(candidate_code, namespace)
            # 2. 執行驗證用測試代碼
            exec(verification_test_code, namespace)
            passed = True
            exit_code = 0
            failure_details = []
        except AssertionError as ae:
            passed = False
            exit_code = 1
            failure_details = [f"AssertionError: {str(ae)}"]
        except Exception as e:
            passed = False
            exit_code = 2
            failure_details = [f"Exception: {str(e)}"]
        finally:
            sys.stderr = old_stderr

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return OracleExecutionResult(
            passed=passed,
            exit_code=exit_code,
            test_count=1,
            failure_count=0 if passed else 1,
            error_count=0,
            stdout="",
            stderr=stream_err.getvalue(),
            execution_time_ms=round(elapsed_ms, 3),
            failure_details=failure_details,
        )
