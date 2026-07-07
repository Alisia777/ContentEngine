from app.intelligence.types import CreativeIntelligencePack, PromptPackOutput, ScriptBriefOutput

__all__ = [
    "CreativeIntelligenceBuilder",
    "ScriptBriefBuilder",
    "PromptPackBuilder",
    "CreativeIntelligencePack",
    "ScriptBriefOutput",
    "PromptPackOutput",
]


def __getattr__(name: str):
    if name == "CreativeIntelligenceBuilder":
        from app.intelligence.insight_builder import CreativeIntelligenceBuilder

        return CreativeIntelligenceBuilder
    if name == "ScriptBriefBuilder":
        from app.intelligence.script_brief_builder import ScriptBriefBuilder

        return ScriptBriefBuilder
    if name == "PromptPackBuilder":
        from app.intelligence.prompt_builder import PromptPackBuilder

        return PromptPackBuilder
    raise AttributeError(name)

