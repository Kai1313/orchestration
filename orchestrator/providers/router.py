from orchestrator.config import OrchestratorConfig
from orchestrator.providers.client import OpenAICompatibleClient

class ModelRouter:
    """
    Routes agent tasks and roles to their configured provider endpoint and model.
    """

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self._clients: dict[str, OpenAICompatibleClient] = {}

    def get_client_for_role(self, role: str) -> OpenAICompatibleClient:
        role_cfg = self.config.roles.get(role)
        if not role_cfg:
            # Fallback to coder role or first available
            role_cfg = self.config.roles.get("coder") or next(iter(self.config.roles.values()))

        provider_cfg = self.config.providers.get(role_cfg.provider)
        if not provider_cfg:
            raise ValueError(f"Provider '{role_cfg.provider}' referenced by role '{role}' is not configured.")

        api_key = provider_cfg.get_api_key()
        if not api_key and provider_cfg.name != "ollama":
            raise ValueError(
                f"Missing API key for provider '{provider_cfg.name}'. "
                f"Please export {provider_cfg.api_key_env} in your environment or .env file."
            )

        client_key = f"{role_cfg.provider}:{role_cfg.model}"
        if client_key not in self._clients:
            self._clients[client_key] = OpenAICompatibleClient(
                base_url=provider_cfg.base_url,
                api_key=api_key or "no-key",
                model=role_cfg.model,
                timeout=float(self.config.test_timeout_seconds) + 30.0,
            )

        return self._clients[client_key]
