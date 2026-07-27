"""
functions/llm/temperature.py — Single source of truth for LLM temperatures.
"""

from enum import Enum
from dataclasses import dataclass

class TaskType(Enum):
    # 🧊 Deterministic — must be consistent and precise
    JOB_SCORING          = "job_scoring"
    RESUME_PARSING       = "resume_parsing"
    SKILL_EXTRACTION     = "skill_extraction"
    JSON_OUTPUT          = "json_output"
    ERROR_DIAGNOSIS      = "error_diagnosis"
    DEDUP_DECISION       = "dedup_decision"

    # ⚖️ Balanced — some reasoning flexibility
    MARKET_ANALYSIS      = "market_analysis"
    QUERY_OPTIMIZATION   = "query_optimization"
    SKILL_GAP_ANALYSIS   = "skill_gap_analysis"
    JOB_SUMMARY          = "job_summary"
    RE_RANKING           = "re_ranking"

    # 🎨 Creative — diversity and natural language
    COVER_LETTER         = "cover_letter"
    CAREER_ADVICE        = "career_advice"
    INTERVIEW_TIPS       = "interview_tips"

@dataclass
class TemperatureConfig:
    temperature: float
    top_p: float = 1.0
    description: str = ""

TEMPERATURE_MAP: dict[TaskType, TemperatureConfig] = {
    # 🧊 Deterministic (0.0 - 0.1)
    TaskType.JOB_SCORING:       TemperatureConfig(0.0, 1.0, "Consistent numeric scoring"),
    TaskType.RESUME_PARSING:    TemperatureConfig(0.1, 1.0, "Faithful text extraction"),
    TaskType.SKILL_EXTRACTION:  TemperatureConfig(0.0, 1.0, "Exact skill identification"),
    TaskType.JSON_OUTPUT:       TemperatureConfig(0.0, 1.0, "Strict JSON compliance"),
    TaskType.ERROR_DIAGNOSIS:   TemperatureConfig(0.0, 1.0, "Precise root cause analysis"),
    TaskType.DEDUP_DECISION:    TemperatureConfig(0.2, 1.0, "Fuzzy match with precision"),

    # ⚖️ Balanced (0.2 - 0.4)
    TaskType.MARKET_ANALYSIS:   TemperatureConfig(0.3, 0.9, "Analytical with insight"),
    TaskType.QUERY_OPTIMIZATION:TemperatureConfig(0.3, 0.9, "Smart query expansion"),
    TaskType.SKILL_GAP_ANALYSIS:TemperatureConfig(0.2, 1.0, "Analytical comparison"),
    TaskType.JOB_SUMMARY:       TemperatureConfig(0.4, 0.9, "Natural but accurate"),
    TaskType.RE_RANKING:        TemperatureConfig(0.1, 1.0, "Consistent re-ordering"),

    # 🎨 Creative (0.5 - 0.8)
    TaskType.COVER_LETTER:      TemperatureConfig(0.7, 0.95, "Varied, engaging writing"),
    TaskType.CAREER_ADVICE:     TemperatureConfig(0.5, 0.9, "Thoughtful suggestions"),
    TaskType.INTERVIEW_TIPS:    TemperatureConfig(0.6, 0.9, "Diverse preparation ideas"),
}

def get_temperature(task: TaskType) -> tuple[float, float]:
    """Returns (temperature, top_p) for a given task."""
    config = TEMPERATURE_MAP[task]
    return config.temperature, config.top_p
