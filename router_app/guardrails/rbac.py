"""
工具角色與權限存取控制 (Tool Role-Based Access Control - RBAC / OWASP LLM03 & LLM06)
落實最小特權原則 (Principle of Least Privilege)：
杜絕普通權限使用者透過 Agent 越權呼叫高風險管理工具或財務交易端點。
"""

from typing import Any, Callable, List, Optional, Tuple
import functools
from ..types import RiskLevel
from ..tools.base_tool import BaseTool


class PermissionDeniedException(Exception):
    """使用者權限不足時拋出的安全例外"""
    pass


def _normalize_roles(roles: Any) -> List[str]:
    """將各類角色格式 (字串、清單、逗號分隔、集合) 統一規範化為小寫字串清單"""
    if not roles:
        return ["user"]
    if isinstance(roles, str):
        return [r.strip().lower() for r in roles.split(",") if r.strip()]
    res = []
    for r in roles:
        if isinstance(r, (list, tuple, set)):
            res.extend([str(x).strip().lower() for x in r if str(x).strip()])
        elif isinstance(r, str):
            res.extend([x.strip().lower() for x in r.split(",") if x.strip()])
        else:
            res.append(str(r).strip().lower())
    return res or ["user"]


def require_roles(*allowed_roles: Any) -> Callable:
    """裝飾器：限制函式或工具必須由具備特定角色的使用者執行"""
    normalized_allowed = set(_normalize_roles(allowed_roles))

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user_roles = kwargs.get("user_roles")
            roles_set = set(_normalize_roles(user_roles))
            if "admin" in roles_set or "root" in roles_set:
                return fn(*args, **kwargs)
            if not roles_set.intersection(normalized_allowed):
                raise PermissionDeniedException(
                    f"權限不足：執行 {fn.__name__} 需要角色 {list(normalized_allowed)}，當前具備 {list(roles_set)}"
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


class ToolRBACGuard:
    """工具層級的角色存取控制守護者"""

    # 預設各風險等級最低要求角色 (當工具未明確指定 allowed_roles 時)
    DEFAULT_RISK_ROLE_MAP = {
        "low": {"guest", "user", "operator", "admin"},
        "medium": {"user", "operator", "admin"},
        "high": {"operator", "admin"},
        "critical": {"admin", "ciso", "security_officer"},
    }

    @classmethod
    def verify_tool_access(
        cls,
        tool: BaseTool,
        user_roles: Any = None,
    ) -> Tuple[bool, str]:
        """
        校驗使用者角色是否具備調用該 Tool 之合法授權
        回傳: (是否允許, 說明訊息)
        """
        roles_set = set(_normalize_roles(user_roles))
        if "admin" in roles_set or "root" in roles_set:
            return True, "Admin access granted."

        # 1. 若工具明確宣告了 allowed_roles
        tool_allowed_roles = getattr(tool, "allowed_roles", None)
        if tool_allowed_roles:
            allowed_set = set(_normalize_roles(tool_allowed_roles))
            if roles_set.intersection(allowed_set):
                return True, f"Role check passed for tool '{tool.name}'."
            return (
                False,
                f"權限不足：調用工具 '{tool.name}' 需要角色 {list(allowed_set)}，但當前使用者僅具備 {list(roles_set)}。",
            )

        # 2. 依工具風險等級推論預設權限
        risk = getattr(tool, "risk_level", "low")
        if hasattr(risk, "value"):
            risk = risk.value
        risk = str(risk).lower()
        required_roles = cls.DEFAULT_RISK_ROLE_MAP.get(risk, {"admin"})

        if roles_set.intersection(required_roles):
            return True, f"Risk-level '{risk}' access granted."

        return (
            False,
            f"權限不足：工具 '{tool.name}' 風險等級為 '{risk}'，需要角色 {list(required_roles)}，拒絕執行以防越權操作。",
        )

    @classmethod
    def enforce(cls, tool: BaseTool, user_roles: Optional[List[str]] = None) -> None:
        """強制校驗，若無權限直接拋出 PermissionDeniedException"""
        allowed, msg = cls.verify_tool_access(tool, user_roles)
        if not allowed:
            raise PermissionDeniedException(msg)
