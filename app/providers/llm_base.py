from typing import Protocol

from app.intelligence.types import GeneratedScriptOutput, ScriptBriefOutput


class LLMProvider(Protocol):
    provider_name: str
    model: str

    def generate_script(self, brief: ScriptBriefOutput) -> GeneratedScriptOutput: ...

