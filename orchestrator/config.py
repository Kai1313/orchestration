import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import yaml

load_dotenv()

class ProviderConfig(BaseModel):
    name: str
    base_url: str
    api_key_env: str
    default_model: str

    def get_api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


class RoleConfig(BaseModel):
    provider: str
    model: str
    protocol: str = "delimited_blocks"  # "delimited_blocks" or "json_tools"


DEFAULT_PROVIDERS = {
    "deepseek": ProviderConfig(
        name="deepseek",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        default_model="anthropic/claude-3.5-sonnet",
    ),
    "gemini": ProviderConfig(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        default_model="gemini-2.5-flash",
    ),
    "ollama": ProviderConfig(
        name="ollama",
        base_url="http://localhost:11434/v1",
        api_key_env="OLLAMA_API_KEY",
        default_model="qwen2.5-coder",
    ),
}

DEFAULT_ROLES = {
    "triage": RoleConfig(provider="gemini", model="gemini-2.5-flash"),
    "reproduce": RoleConfig(provider="deepseek", model="deepseek-chat"),
    "planner": RoleConfig(provider="deepseek", model="deepseek-chat"),
    "coder": RoleConfig(provider="openrouter", model="anthropic/claude-3.5-sonnet"),
    "reviewer": RoleConfig(provider="deepseek", model="deepseek-chat"),
}


class OrchestratorConfig(BaseModel):
    providers: dict[str, ProviderConfig] = Field(default_factory=lambda: DEFAULT_PROVIDERS.copy())
    roles: dict[str, RoleConfig] = Field(default_factory=lambda: DEFAULT_ROLES.copy())
    max_cost_usd: float = 2.00
    max_tokens: int = 500_000
    test_timeout_seconds: int = 60
    max_edit_retries: int = 3
    max_plan_backtracks: int = 2
    interactive_timeout: float | None = 300.0
    docker_image: str | None = None


def load_config(config_path: str | Path | None = None) -> OrchestratorConfig:
    """Loads configuration from YAML or returns default settings."""
    search_paths = []
    if config_path:
        search_paths.append(Path(config_path).resolve())
    search_paths.append(Path("orchestrator.yaml").resolve())
    search_paths.append(Path.home() / ".orchestrator" / "config.yaml")

    for p in search_paths:
        if p.exists():
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                return OrchestratorConfig(**data)
            except Exception:
                pass

    return OrchestratorConfig()
