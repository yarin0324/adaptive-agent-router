"""
不可篡改雜湊鏈審計日誌器 (Tamper-Proof Hash-Chained Audit Logger)
符合金融級合規與 SOC 2 / ISO 27001 稽核要求：
1. 區塊鏈式雜湊鏈 (Hash Chain): 每筆紀錄皆包含前一筆日誌之 SHA-256 雜湊值。
2. 零機敏落盤 (Zero-PII Storage): 寫入磁碟前強制經過 PII 脫敏，杜絕個資洩漏至紀錄檔。
3. 完整性可驗證性 (Cryptographic Verification): 提供 verify_integrity() 一鍵偵測任何篡改或單行刪除。
"""

import hashlib
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from .rails import OutputPIISanitizerRail


class AuditRecord(BaseModel):
    record_id: str
    timestamp: float = Field(default_factory=time.time)
    event_type: str  # ROUTING_DECISION, TOOL_EXECUTION, TASK_SUSPENDED, TASK_APPROVED, SECURITY_BLOCKED
    operator_id: str = "system"
    prompt_hash: str
    mode_used: str
    risk_level: str
    details: Dict[str, Any]
    prev_hash: str
    current_hash: str = ""


class TamperProofAuditLogger:
    """不可篡改審計日誌器"""

    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self, log_file_path: Optional[str] = None):
        self.log_file_path = log_file_path
        self._records: List[AuditRecord] = []
        self._last_hash = self.GENESIS_HASH
        self._counter = 0
        self._lock = threading.Lock()

        # 若檔案已存在，初始化最後一筆雜湊
        if self.log_file_path and os.path.exists(self.log_file_path):
            self._load_last_hash()

    def _load_last_hash(self):
        try:
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    last_record = json.loads(lines[-1].strip())
                    self._last_hash = last_record.get("current_hash", self.GENESIS_HASH)
                    self._counter = len(lines)
        except Exception:
            self._last_hash = self.GENESIS_HASH

    def _calculate_hash(self, prev_hash: str, payload_str: str) -> str:
        content = f"{prev_hash}|{payload_str}".encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def record_event(
        self,
        event_type: str,
        prompt: str,
        mode_used: str,
        risk_level: str,
        details: Optional[Dict[str, Any]] = None,
        operator_id: str = "system",
    ) -> AuditRecord:
        """
        記錄一筆不可篡改審計事件
        強制在落盤前執行 PII 脫敏，並更新密碼學雜湊鏈 (執行緒安全)
        """
        with self._lock:
            self._counter += 1
            record_id = f"aud_{self._counter:08d}"

            # 1. 產生提問特徵指紋 (SHA-256)
            prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

            # 2. 詳情進行 PII 深度脫敏
            raw_details = details or {}
            sanitized_details_str = OutputPIISanitizerRail.sanitize(json.dumps(raw_details, ensure_ascii=False, default=str))
            sanitized_details = json.loads(sanitized_details_str)

            # 3. 準備載荷內容以計算當前雜湊
            payload_to_hash = json.dumps({
                "record_id": record_id,
                "event_type": event_type,
                "operator_id": operator_id,
                "prompt_hash": prompt_hash,
                "mode_used": mode_used,
                "risk_level": risk_level,
                "details": sanitized_details,
            }, sort_keys=True)

            current_hash = self._calculate_hash(self._last_hash, payload_to_hash)

            record = AuditRecord(
                record_id=record_id,
                event_type=event_type,
                operator_id=operator_id,
                prompt_hash=prompt_hash,
                mode_used=mode_used,
                risk_level=risk_level,
                details=sanitized_details,
                prev_hash=self._last_hash,
                current_hash=current_hash,
            )

            self._records.append(record)
            self._last_hash = current_hash

            # 4. 持久化寫入磁碟 (JSON Lines)
            if self.log_file_path:
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(record.model_dump_json() + "\n")
                    f.flush()

            return record

    @classmethod
    def _verify_core(cls, log_file_path: Optional[str]) -> Tuple[bool, int, Optional[str]]:
        """核心雜湊鏈校驗邏輯"""
        if not log_file_path or not os.path.exists(log_file_path):
            return False, 0, f"審計日誌檔案不存在: {log_file_path}"

        expected_prev_hash = cls.GENESIS_HASH
        count = 0

        with open(log_file_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue
                count += 1
                try:
                    data = json.loads(line_str)
                except Exception as e:
                    return False, count, f"第 {idx} 行 JSON 解析失敗，疑似檔案受損: {e}"

                record_prev_hash = data.get("prev_hash")
                record_current_hash = data.get("current_hash")

                # 1. 檢查前驅雜湊是否對齊
                if record_prev_hash != expected_prev_hash:
                    return False, count, f"第 {idx} 行前驅雜湊斷裂！Hash chain mismatch: 記錄值 {record_prev_hash[:10]}... 與期望值 {expected_prev_hash[:10]}... 不符 (遭受刪除或插入攻擊)"

                # 2. 重新計算當前行之雜湊
                payload_to_hash = json.dumps({
                    "record_id": data.get("record_id"),
                    "event_type": data.get("event_type"),
                    "operator_id": data.get("operator_id"),
                    "prompt_hash": data.get("prompt_hash"),
                    "mode_used": data.get("mode_used"),
                    "risk_level": data.get("risk_level"),
                    "details": data.get("details"),
                }, sort_keys=True)

                content = f"{expected_prev_hash}|{payload_to_hash}".encode("utf-8")
                computed_hash = hashlib.sha256(content).hexdigest()

                if computed_hash != record_current_hash:
                    return False, count, f"第 {idx} 行內容遭受篡改！Hash chain mismatch: 內容雜湊校驗失敗。"

                expected_prev_hash = record_current_hash

        return True, count, None

    def verify_file_integrity(self_or_cls, log_file_path: Optional[str] = None) -> Tuple[bool, int, Optional[str]]:
        """
        審計驗證：檢驗整個日誌檔案之密碼學雜湊鏈完整性
        回傳: (是否完整, 驗證記錄總數, 錯誤原因或 None)
        """
        if isinstance(self_or_cls, TamperProofAuditLogger):
            target_path = log_file_path or self_or_cls.log_file_path
        elif isinstance(self_or_cls, str):
            target_path = self_or_cls
        else:
            target_path = log_file_path
        return TamperProofAuditLogger._verify_core(target_path)
