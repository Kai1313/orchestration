from rich.console import Console
from orchestrator.config import OrchestratorConfig, RoleConfig
from orchestrator.providers.client import OpenAICompatibleClient, LLMResponse, ProviderFatalError

console = Console()

class ModelRouter:
    """
    Routes agent tasks and roles to their configured provider endpoint and model.
    Supports prioritized fallback chains, instant failovers, and sticky session routing.
    """

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self._clients: dict[str, OpenAICompatibleClient] = {}
        self.active_role_indices: dict[str, int] = {}

    def get_role_candidates(self, role: str) -> list[RoleConfig]:
        role_cfg = self.config.roles.get(role)
        if not role_cfg:
            role_cfg = self.config.roles.get("coder") or next(iter(self.config.roles.values()))
        candidates = [role_cfg]
        if hasattr(role_cfg, "fallbacks") and role_cfg.fallbacks:
            candidates.extend(role_cfg.fallbacks)
        return candidates

    def get_active_role_config(self, role: str) -> RoleConfig:
        candidates = self.get_role_candidates(role)
        idx = self.active_role_indices.get(role, 0)
        if idx >= len(candidates):
            idx = len(candidates) - 1
        return candidates[idx]

    def failover_role(self, role: str, reason: str = "") -> bool:
        """
        Advances the role to the next configured fallback provider in its chain.
        Returns True if a new fallback provider was activated, False if candidates are exhausted.
        """
        candidates = self.get_role_candidates(role)
        current_idx = self.active_role_indices.get(role, 0)
        next_idx = current_idx + 1

        if next_idx < len(candidates):
            old_cfg = candidates[current_idx]
            new_cfg = candidates[next_idx]
            self.active_role_indices[role] = next_idx
            console.print(
                f"[bold yellow]Provider failover for role '{role}': "
                f"switching from {old_cfg.provider}/{old_cfg.model} -> {new_cfg.provider}/{new_cfg.model} "
                f"({reason})[/bold yellow]"
            )
            return True
        return False

    def get_client_for_role(self, role: str) -> OpenAICompatibleClient:
        role_cfg = self.get_active_role_config(role)
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

    async def complete_for_role(
        self,
        role: str,
        messages: list[dict],
        **kwargs,
    ) -> LLMResponse:
        """
        Completes an LLM request for a given role, automatically executing failover
        to fallback providers if fatal errors or retry exhaustions occur.
        """
        while True:
            client = self.get_client_for_role(role)
            try:
                return await client.complete(messages, **kwargs)
            except (ProviderFatalError, RuntimeError) as e:
                can_failover = self.failover_role(role, reason=str(e))
                if not can_failover:
                    raise

    def get_sticky_state(self) -> dict[str, dict[str, str]]:
        """Returns the active provider configuration for any roles that experienced failover."""
        state = {}
        for role, idx in self.active_role_indices.items():
            cfg = self.get_active_role_config(role)
            state[role] = {"provider": cfg.provider, "model": cfg.model}
        return state

    def restore_sticky_state(self, saved_providers: dict[str, dict[str, str]]) -> None:
        """Restores active provider indices based on checkpoint state."""
        for role, target in (saved_providers or {}).items():
            candidates = self.get_role_candidates(role)
            for idx, cand in enumerate(candidates):
                if cand.provider == target.get("provider") and cand.model == target.get("model"):
                    self.active_role_indices[role] = idx
                    break
