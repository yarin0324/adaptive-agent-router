"""
鏈路可觀測性與追蹤器 (Observability & Distributed Tracing)
相容 OpenTelemetry 設計哲學，提供 Trace ID 與 Span 生命週期追蹤，便於生產環境監控與日誌收集。
"""

import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TraceSpan(BaseModel):
    span_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    status: str = "RUNNING"  # RUNNING, OK, ERROR

    def finish(self, status: str = "OK"):
        self.end_time = time.time()
        self.status = status

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return round((self.end_time - self.start_time) * 1000, 2)
        return round((time.time() - self.start_time) * 1000, 2)


class TraceContext:
    """任務追蹤上下文"""

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.spans: List[TraceSpan] = []

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> TraceSpan:
        span = TraceSpan(name=name, attributes=attributes or {})
        self.spans.append(span)
        return span

    def export(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_count": len(self.spans),
            "spans": [
                {
                    "span_id": s.span_id,
                    "name": s.name,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                    "attributes": s.attributes,
                }
                for s in self.spans
            ],
        }
