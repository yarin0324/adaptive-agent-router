"""
自適應 RAG 調度適配器自動化單元測試套件 (Comprehensive Adaptive RAG Test Suite)
檢驗五大策略 (No-RAG, Fast Hybrid, Precision, CRAG, Multi-Hop) 與三階級聯路由器之極限邊界。
"""

import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_app import (
    AdaptiveAgentDispatcher,
    AdaptiveRAGAdapter,
    AdaptiveRAGRouter,
    BaseRetriever,
    InMemoryVectorRetriever,
    RAGMode,
    RetrievedChunk,
    NoRAGStrategy,
    FastHybridRAGStrategy,
    PrecisionRerankRAGStrategy,
    CorrectiveRAGStrategy,
    AgenticMultiHopRAGStrategy,
)


class TestAdaptiveRAGSuite(unittest.TestCase):

    def setUp(self):
        self.docs = [
            {"id": "doc_tax", "content": "統一編號為 28459201，發票抬頭為鴻昇數位科技有限公司。", "source": "tax.md"},
            {"id": "doc_nda", "content": "保密條款規定違約金新台幣 500 萬元，禁止對第三方披露。", "source": "nda.md"},
            {"id": "doc_rev_2024", "content": "2024 年全年度總營收為新台幣 3.6 億元。", "source": "fin2024.md"},
            {"id": "doc_rev_2025", "content": "2025 年全年度總營收成長至新台幣 5.8 億元。", "source": "fin2025.md"},
        ]
        self.retriever = InMemoryVectorRetriever(documents=self.docs)
        self.adapter = AdaptiveRAGAdapter(retriever=self.retriever)

    def test_no_rag_strategy(self):
        """測試 No-RAG 策略：閒聊或代碼演算直接放行，返回空切片與 0ms"""
        strategy = NoRAGStrategy()
        res = strategy.execute("請用 Python 寫一個快速排序演算法", self.retriever)
        self.assertEqual(res.mode_used, RAGMode.NO_RAG)
        self.assertEqual(len(res.chunks), 0)
        self.assertEqual(res.confidence_score, 1.0)
        self.assertFalse(res.fallback_triggered)

    def test_fast_hybrid_strategy(self):
        """測試 Fast Hybrid 策略：BM25 + 向量 RRF 倒數排名融合"""
        strategy = FastHybridRAGStrategy(top_k=2)
        res = strategy.execute("請查詢統一編號是多少", self.retriever)
        self.assertEqual(res.mode_used, RAGMode.FAST_HYBRID)
        self.assertGreaterEqual(len(res.chunks), 1)
        self.assertEqual(res.chunks[0].id, "doc_tax")
        self.assertIn("28459201", res.chunks[0].content)

    def test_precision_rerank_strategy(self):
        """測試 Precision Rerank 策略：二階段交叉特徵重排序與低分過濾"""
        strategy = PrecisionRerankRAGStrategy(top_k=2, min_rerank_score=0.1)
        res = strategy.execute("保密條款的違約金賠償是多少", self.retriever)
        self.assertEqual(res.mode_used, RAGMode.PRECISION_RERANK)
        self.assertGreaterEqual(len(res.chunks), 1)
        self.assertEqual(res.chunks[0].id, "doc_nda")
        self.assertIn("500 萬元", res.chunks[0].content)

    def test_corrective_crag_strategy(self):
        """測試 Corrective RAG (CRAG)：口語去噪與二次提問重寫"""
        strategy = CorrectiveRAGStrategy(upper_threshold=0.5, lower_threshold=0.05, top_k=2)
        # 帶有口語雜訊的提問
        res = strategy.execute("請問一下我想了解公司統一編號", self.retriever)
        self.assertEqual(res.mode_used, RAGMode.CORRECTIVE_CRAG)
        self.assertIsNotNone(res.transformed_query)
        self.assertNotIn("請問一下", res.transformed_query)

        # 測試知識庫完全沒有的荒謬提問 (應該觸發 Incorrect Fallback)
        strategy_strict = CorrectiveRAGStrategy(upper_threshold=0.8, lower_threshold=0.5)
        res_fail = strategy_strict.execute("火星殖民基地的核聚變反應爐型號", self.retriever)
        self.assertTrue(res_fail.fallback_triggered)
        self.assertEqual(len(res_fail.chunks), 0)

    def test_agentic_multihop_strategy(self):
        """測試 Agentic Multi-Hop 策略：跨年份/多實體子問題自動拆解"""
        strategy = AgenticMultiHopRAGStrategy(top_k_per_hop=2)
        res = strategy.execute("比較 2024 與 2025 年的營收差異", self.retriever)
        self.assertEqual(res.mode_used, RAGMode.AGENTIC_MULTIHOP)
        self.assertGreaterEqual(res.metadata["hops_count"], 2)
        
        # 驗證兩年的切片皆被成功探勘
        chunk_ids = {c.id for c in res.chunks}
        self.assertIn("doc_rev_2024", chunk_ids)
        self.assertIn("doc_rev_2025", chunk_ids)

    def test_adaptive_rag_router_decisions(self):
        """測試 AdaptiveRAGRouter 三階級聯分流準確性"""
        router = AdaptiveRAGRouter()

        # 閒聊問候 -> NO_RAG
        dec_chat = router.route("早安！你好！")
        self.assertEqual(dec_chat.mode, RAGMode.NO_RAG)

        # 代碼推導 -> NO_RAG
        dec_code = router.route("幫我寫一個反轉字串的 python 函式")
        self.assertEqual(dec_code.mode, RAGMode.NO_RAG)

        # 比較多實體 -> AGENTIC_MULTIHOP
        dec_compare = router.route("請比較 A 公司與 B 公司的營收差異")
        self.assertEqual(dec_compare.mode, RAGMode.AGENTIC_MULTIHOP)

        # 法規條款 -> PRECISION_RERANK
        dec_legal = router.route("審查保密條款與智慧財產權合約罰則")
        self.assertEqual(dec_legal.mode, RAGMode.PRECISION_RERANK)

        # 口語模糊 -> CORRECTIVE_CRAG
        dec_crag = router.route("我想了解一下好像有提到什麼政策")
        self.assertEqual(dec_crag.mode, RAGMode.CORRECTIVE_CRAG)

        # 明確事實查詢 -> FAST_HYBRID
        dec_fact = router.route("查詢公司統一編號與發票抬頭")
        self.assertEqual(dec_fact.mode, RAGMode.FAST_HYBRID)

    def test_dispatcher_dual_engine_integration(self):
        """測試 AdaptiveAgentDispatcher 與 AdaptiveRAGAdapter 雙軸一體化調度"""
        dispatcher = AdaptiveAgentDispatcher(
            rag_adapter=self.adapter,
            enable_logging=False
        )
        res = dispatcher.process("請查詢公司統一編號是多少")
        self.assertTrue(res.success)
        self.assertIn("rag", res.metadata)
        self.assertEqual(res.metadata["rag"]["strategy"], "fast_hybrid")
        self.assertGreaterEqual(res.metadata["rag"]["chunks_count"], 1)


if __name__ == "__main__":
    unittest.main()
