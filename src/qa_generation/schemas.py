from typing import List
from pydantic import BaseModel, Field

class QAPair(BaseModel):
    """单个问答对的数据结构"""
    type: str = Field(
        description="Must be one of: formula_derivation | physical_principle | algorithm_design"
    )
    difficulty: int = Field(
        description="Difficulty level of the question from 1 (basic concept) to 5 (complex mathematical derivation or system architecture)"
    )
    chain_of_reasoning: str = Field(
        description="Step-by-step logical deduction or physical analysis before formulating the final answer. This is your internal thought process based strictly on the chunk."
    )
    question: str = Field(
        description="A high-quality, context-aware question grounded in the given chunk. Must be in formal academic English."
    )
    answer: str = Field(
        description="A rigorous and detailed answer grounded in the chunk, preserving original LaTeX formulas. Must be in formal academic English."
    )
    reference_quote: str = Field(
        description="A short quote extracted from the original content to ground the QA (no more than 50 words)."
    )

class QACollection(BaseModel):
    """用于接收大模型返回的整个 JSON 数组结构"""
    qa_list: List[QAPair] = Field(
        description="List of QA pairs. Return an empty list [] if the chunk contains no substantial technical content (e.g., pure references, acknowledgments)."
    )