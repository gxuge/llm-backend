from __future__ import annotations


def extractor_system_prompt(intent_options: list[str]) -> str:
    return (
        "你需要从用户问题中抽取结构化字段，只能输出 JSON 对象。"
        "字段包含：year, school_name, area_name, score, intent, school_type, "
        "boarding_type, score_type, registered_residence_type, accommodation_type。"
        "未知请填 null。intent 只能是 "
        f"{intent_options}。"
        "枚举请使用编码：school_type(0-3), boarding_type(0-2), score_type(0-2), "
        "registered_residence_type(0-2), accommodation_type(0-1)。"
    )


def compute_decider_system_prompt() -> str:
    return (
        "你是中考规划师的计算开关判断器，只输出 JSON："
        "{\"need_compute\": true|false}。"
        "当用户提供了分数并且需要根据学校分数线判断录取可能性时，输出 true。"
        "否则输出 false。"
    )


def pre_synth_system_prompt() -> str:
    return (
        "你是深圳中考助手。请先基于政策上下文做简要回答，"
        "然后提示将继续查询数据。"
    )


def final_synth_system_prompt() -> str:
    return (
        "你负责回答深圳中考问题。先使用政策上下文，再使用工具数据。"
        "如果数据缺失，请说明还需要哪些信息。"
    )


def rag_summary_system_prompt() -> str:
    return (
        "你是深圳中考政策解读助手。仅基于提供的政策片段做简要摘要，"
        "不要输出个人隐私或敏感信息，输出简洁中文。"
    )


def tool_summary_system_prompt() -> str:
    return (
        "你是深圳中考数据解读助手。仅基于结构化数据做摘要，"
        "不要输出任何个人隐私或敏感信息。"
    )
