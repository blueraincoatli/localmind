#!/usr/bin/env python3
"""
LocalMind LongMemEval 基准测试 (Phase 7)
评估召回精度，目标 >90% R@5

LongMemEval 是一个长对话记忆基准测试：
- 包含多轮对话
- 每个对话后有相关问题
- 测试模型是否能召回早期对话中的信息

数据集格式（预期）:
[
  {
    "conversation_id": "conv_001",
    "messages": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."}
    ],
    "questions": [
      {
        "question": "用户之前说了什么？",
        "answer": "...",
        "relevant_turns": [0, 2]
      }
    ]
  }
]
"""

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from localmind.config import config
from recall.engine import RecallEngine
from write.writer import MemoryWriter
from write.analyzer import MemoryAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [bench] %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    total_questions: int = 0
    correct_at_1: int = 0  # R@1
    correct_at_5: int = 0  # R@5
    correct_at_10: int = 0  # R@10
    
    # 详细结果
    details: List[Dict] = field(default_factory=list)
    
    @property
    def recall_at_1(self) -> float:
        return self.correct_at_1 / max(self.total_questions, 1)
    
    @property
    def recall_at_5(self) -> float:
        return self.correct_at_5 / max(self.total_questions, 1)
    
    @property
    def recall_at_10(self) -> float:
        return self.correct_at_10 / max(self.total_questions, 1)
    
    def report(self) -> str:
        """生成报告"""
        lines = [
            "=" * 60,
            "LongMemEval 基准测试报告",
            "=" * 60,
            f"总问题数: {self.total_questions}",
            f"",
            f"R@1:  {self.recall_at_1:.1%} ({self.correct_at_1}/{self.total_questions})",
            f"R@5:  {self.recall_at_5:.1%} ({self.correct_at_5}/{self.total_questions})",
            f"R@10: {self.recall_at_10:.1%} ({self.correct_at_10}/{self.total_questions})",
            "=" * 60,
        ]
        return "\n".join(lines)


class LongMemEvalBenchmark:
    """LongMemEval 基准测试器"""
    
    def __init__(self):
        self.engine = RecallEngine()
        self.writer = MemoryWriter()
        self.analyzer = MemoryAnalyzer()
    
    def load_dataset(self, dataset_path: Optional[str] = None) -> List[Dict]:
        """
        加载 LongMemEval 数据集
        
        如果没有提供数据集，生成一个迷你测试集
        """
        if dataset_path and Path(dataset_path).exists():
            with open(dataset_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 生成迷你测试集（用于快速验证）
        logger.info("使用迷你测试集（真实测试需要下载完整数据集）")
        return self._generate_mini_dataset()
    
    def _generate_mini_dataset(self) -> List[Dict]:
        """生成迷你测试集"""
        return [
            {
                "conversation_id": "mini_001",
                "messages": [
                    {"role": "user", "content": "我叫Alice，是一名设计师"},
                    {"role": "assistant", "content": "你好Alice，很高兴认识你"},
                    {"role": "user", "content": "我喜欢简约风格的设计"},
                    {"role": "assistant", "content": "简约风格很经典"},
                    {"role": "user", "content": "我最近在学习编程"},
                ],
                "questions": [
                    {
                        "question": "用户叫什么名字？",
                        "answer": "Alice",
                        "keywords": ["Alice", "名字"],
                        "relevant_turns": [0]
                    },
                    {
                        "question": "用户的职业是什么？",
                        "answer": "设计师",
                        "keywords": ["设计师", "职业"],
                        "relevant_turns": [0]
                    },
                    {
                        "question": "用户喜欢什么风格？",
                        "answer": "简约风格",
                        "keywords": ["简约", "风格"],
                        "relevant_turns": [2]
                    }
                ]
            },
            {
                "conversation_id": "mini_002",
                "messages": [
                    {"role": "user", "content": "我是一个内向的人"},
                    {"role": "assistant", "content": "内向也是一种特质"},
                    {"role": "user", "content": "我喜欢独处，不喜欢社交"},
                    {"role": "assistant", "content": "独处可以让人充电"},
                    {"role": "user", "content": "我在学习Python编程"},
                ],
                "questions": [
                    {
                        "question": "用户性格如何？",
                        "answer": "内向",
                        "keywords": ["内向", "性格"],
                        "relevant_turns": [0, 2]
                    },
                    {
                        "question": "用户喜欢什么？",
                        "answer": "独处",
                        "keywords": ["独处"],
                        "relevant_turns": [2]
                    }
                ]
            }
        ]
    
    def ingest_conversation(self, conversation: Dict) -> bool:
        """
        将对话摄入记忆系统
        
        模拟真实的记忆写入流程
        """
        try:
            conv_id = conversation["conversation_id"]
            messages = conversation["messages"]
            
            # 转换为文本格式
            conv_text = "\n".join([
                f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
                for m in messages
            ])
            
            # 使用写入引擎（结构化 + verbatim）
            analysis = self.analyzer.analyze(conv_text)
            result = self.writer.write_analysis_with_verbatim(
                analysis=analysis,
                conversation=conv_text,
                conversation_id=conv_id
            )
            
            logger.debug(f"摄入对话 {conv_id}: "
                        f"structured={len(result['structured_ids'])}, "
                        f"verbatim={len(result['verbatim_ids'])}")
            return True
            
        except Exception as e:
            logger.error(f"摄入对话失败: {e}")
            return False
    
    def evaluate_question(self, question: Dict, conversation_id: str) -> Dict:
        """
        评估单个问题
        
        召回相关记忆，检查是否包含答案关键词
        """
        query = question["question"]
        keywords = question.get("keywords", [])
        
        # 召回记忆
        ctx = self.engine.recall(query, conversation_id, top_k=10)
        
        # 提取召回内容
        recalled_contents = []
        for result in ctx.recalled_results:
            for record in result.records:
                recalled_contents.append(record.content.lower())
        
        # 检查是否包含关键词（简单匹配）
        matches_at = {}
        for k in [1, 5, 10]:
            contents = " ".join(recalled_contents[:k])
            match_count = sum(1 for kw in keywords if kw.lower() in contents)
            matches_at[k] = match_count >= max(1, len(keywords) // 2)
        
        return {
            "question": query,
            "keywords": keywords,
            "matches_at_1": matches_at[1],
            "matches_at_5": matches_at[5],
            "matches_at_10": matches_at[10],
            "recalled_dims": [r.dimension_id for r in ctx.recalled_results[:5]],
        }
    
    def run(self, dataset_path: Optional[str] = None) -> BenchmarkResult:
        """
        运行完整基准测试
        """
        dataset = self.load_dataset(dataset_path)
        result = BenchmarkResult()
        
        logger.info(f"开始基准测试，{len(dataset)} 个对话")
        
        for conv in dataset:
            conv_id = conv["conversation_id"]
            
            # 1. 摄入对话
            logger.info(f"摄入对话: {conv_id}")
            self.ingest_conversation(conv)
            
            # 2. 评估每个问题
            for question in conv.get("questions", []):
                eval_result = self.evaluate_question(question, conv_id)
                
                result.total_questions += 1
                if eval_result["matches_at_1"]:
                    result.correct_at_1 += 1
                if eval_result["matches_at_5"]:
                    result.correct_at_5 += 1
                if eval_result["matches_at_10"]:
                    result.correct_at_10 += 1
                
                result.details.append(eval_result)
                
                logger.debug(f"问题: {question['question'][:30]}... "
                           f"R@1={eval_result['matches_at_1']}, "
                           f"R@5={eval_result['matches_at_5']}")
        
        return result


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LongMemEval 基准测试")
    parser.add_argument("--dataset", type=str, help="数据集路径（JSON）")
    parser.add_argument("--output", type=str, help="结果输出路径")
    args = parser.parse_args()
    
    print("=" * 60)
    print("LocalMind LongMemEval 基准测试")
    print("=" * 60)
    print()
    
    # 运行测试
    benchmark = LongMemEvalBenchmark()
    result = benchmark.run(args.dataset)
    
    # 打印报告
    print(result.report())
    
    # 保存结果
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "total_questions": result.total_questions,
                "recall_at_1": result.recall_at_1,
                "recall_at_5": result.recall_at_5,
                "recall_at_10": result.recall_at_10,
                "details": result.details,
                "timestamp": datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存: {output_path}")
    
    # 返回码
    return 0 if result.recall_at_5 >= 0.5 else 1  # 迷你测试期望 >50%


if __name__ == "__main__":
    sys.exit(main())
