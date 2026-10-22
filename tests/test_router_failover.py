import pytest
from unittest.mock import AsyncMock, patch
from orchestrator.config import OrchestratorConfig, RoleConfig, ProviderConfig
from orchestrator.providers.router import ModelRouter
from orchestrator.providers.client import LLMResponse, ProviderFatalError

@pytest.mark.asyncio
async def test_router_instant_failover():
    cfg = OrchestratorConfig(
        providers={
            "gemini": ProviderConfig(
                name="gemini",
                base_url="https://gemini.mock/v1",
                api_key_env="GEMINI_API_KEY",
                default_model="gemini-3.8-flash",
            ),
            "deepseek": ProviderConfig(
                name="deepseek",
                base_url="https://deepseek.mock/v1",
                api_key_env="DEEPSEEK_API_KEY",
                default_model="deepseek-chat",
            ),
        },
        roles={
            "triage": RoleConfig(
                provider="gemini",
                model="gemini-3.8-flash",
                fallbacks=[
                    RoleConfig(provider="deepseek", model="deepseek-chat")
                ],
            )
        },
    )

    with patch.dict("os.environ", {"GEMINI_API_KEY": "g-key", "DEEPSEEK_API_KEY": "d-key"}):
        router = ModelRouter(cfg)

        # First client (Gemini) will throw 503 ProviderFatalError
        mock_gemini_client = AsyncMock()
        mock_gemini_client.complete.side_effect = ProviderFatalError(503, "High Demand")

        # Second client (DeepSeek) will succeed
        mock_deepseek_client = AsyncMock()
        mock_deepseek_client.complete.return_value = LLMResponse(
            content="Triage analysis via DeepSeek",
            prompt_tokens=100,
            completion_tokens=50,
            finish_reason="stop",
            model="deepseek-chat",
        )

        def mock_get_client(role: str):
            active_cfg = router.get_active_role_config(role)
            if active_cfg.provider == "gemini":
                return mock_gemini_client
            return mock_deepseek_client

        router.get_client_for_role = mock_get_client

        # Call complete_for_role
        resp = await router.complete_for_role("triage", [{"role": "user", "content": "triage repo"}])

        assert resp.content == "Triage analysis via DeepSeek"
        assert resp.model == "deepseek-chat"

        # Verify sticky session: router should now remember deepseek as active for triage
        active = router.get_sticky_state()
        assert active["triage"]["provider"] == "deepseek"
        assert active["triage"]["model"] == "deepseek-chat"

        # Verify restoration
        new_router = ModelRouter(cfg)
        new_router.restore_sticky_state(active)
        assert new_router.get_active_role_config("triage").provider == "deepseek"
