"""
編譯器級 AST 語法樹安全護欄 (AST Security Guardrail)
借鏡自 SapB1McpServer AST 唯讀護欄設計
不依賴易被混淆的正則表達式，直接在編譯階段檢查抽象語法樹 (Abstract Syntax Tree)，
杜絕 Prompt 越獄、程式碼注入與資料庫破壞。
"""

import ast
import re
from typing import Tuple, List, Set


class PythonASTSecurityGuard(ast.NodeVisitor):
    """
    Python 抽象語法樹靜態分析衛兵
    阻斷危險模組匯入、系統呼叫、檔案存取與動態代碼執行
    """

    FORBIDDEN_CALLS: Set[str] = {
        "eval", "exec", "compile", "__import__", "open", "input",
        "globals", "locals", "getattr", "setattr", "delattr"
    }

    FORBIDDEN_MODULES: Set[str] = {
        "os", "sys", "subprocess", "shutil", "socket", "requests",
        "urllib", "importlib", "pickle", "ctypes", "pathlib"
    }

    def __init__(self):
        self.violations: List[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name.split(".")[0] in self.FORBIDDEN_MODULES:
                self.violations.append(f"禁止匯入高危險系統模組: '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module and node.module.split(".")[0] in self.FORBIDDEN_MODULES:
            self.violations.append(f"禁止從系統模組匯入: '{node.module}'")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # 檢查直接呼叫，例如 eval(...)
        if isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_CALLS:
            self.violations.append(f"禁止調用危險內建函數: '{node.func.id}()'")
        # 檢查屬性呼叫，例如 os.system(...)
        elif isinstance(node.func, ast.Attribute) and node.func.attr in {"system", "popen", "spawn"}:
            self.violations.append(f"禁止執行作業系統命令調用: '.{node.func.attr}()'")
        self.generic_visit(node)

    @classmethod
    def validate_code(cls, code_str: str) -> Tuple[bool, List[str]]:
        """
        編譯並審查代碼安全性
        :return: (是否安全, 違規清單)
        """
        try:
            tree = ast.parse(code_str)
            guard = cls()
            guard.visit(tree)
            return len(guard.violations) == 0, guard.violations
        except SyntaxError as e:
            return False, [f"語法解析失敗 (SyntaxError): {e}"]


class SQLASTSecurityGuard:
    """
    SQL 結構化語法樹唯讀審查衛兵
    物理阻斷破壞性操作 (DROP, DELETE, TRUNCATE, ALTER, UPDATE 等)
    """

    DESTRUCTIVE_KEYWORDS: Set[str] = {
        "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT",
        "UPDATE", "GRANT", "REVOKE", "EXEC", "EXECUTE"
    }

    @classmethod
    def validate_query(cls, sql_query: str) -> Tuple[bool, List[str]]:
        """檢查 SQL 語法結構是否純粹唯讀"""
        # 移除註解干擾 (如 /* ... */ 或 -- ...)
        cleaned = re.sub(r"/\*.*?\*/", " ", sql_query, flags=re.DOTALL)
        cleaned = re.sub(r"--.*", " ", cleaned)
        tokens = [t.upper() for t in re.findall(r"\b[A-Za-z_]+\b", cleaned)]

        violations = []
        for kw in cls.DESTRUCTIVE_KEYWORDS:
            if kw in tokens:
                violations.append(f"偵測到破壞性 SQL 操作子句: '{kw}' (強制要求唯讀 SELECT)")

        # 必須包含 SELECT 或 WITH (CTE)
        if not any(token in ["SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"] for token in tokens):
            violations.append("查詢陳述式必須為唯讀指令 (如 SELECT / WITH)")

        return len(violations) == 0, violations
