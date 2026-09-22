import httpx
import pytest

from app.services import foundry_client


def test_missing_foundry_configuration_is_rejected(monkeypatch) -> None:
    for variable in (
        "FOUNDRY_PROJECT_ENDPOINT",
        "FOUNDRY_API_KEY",
        "FOUNDRY_MODEL_NAME",
    ):
        monkeypatch.delenv(variable, raising=False)
    foundry_client.get_foundry_config.cache_clear()

    with pytest.raises(foundry_client.FoundryConfigurationError):
        foundry_client.get_foundry_config()


def test_foundry_configuration_loads_without_exposing_key(monkeypatch) -> None:
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://resource.services.ai.azure.com/api/projects/project",
    )
    monkeypatch.setenv("FOUNDRY_API_KEY", "test-secret-key")
    monkeypatch.setenv("FOUNDRY_MODEL_NAME", "vision-deployment")
    monkeypatch.setenv("FOUNDRY_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("FOUNDRY_MAX_RETRIES", "3")
    foundry_client.get_foundry_config.cache_clear()

    config = foundry_client.get_foundry_config()

    assert config.project_endpoint.endswith("/api/projects/project")
    assert config.model_name == "vision-deployment"
    assert config.timeout_seconds == 12
    assert config.max_retries == 3
    assert "test-secret-key" not in repr(config)


def test_client_initialization_uses_project_responses_endpoint() -> None:
    config = foundry_client.FoundryConfig(
        project_endpoint="https://resource.services.ai.azure.com/api/projects/project",
        api_key="test-secret-key",
        model_name="vision-deployment",
        timeout_seconds=5,
        max_retries=1,
    )

    client = foundry_client.FoundryClient(config)

    assert client.responses_url.endswith("/openai/v1/responses")


def test_successful_foundry_response_is_normalized(monkeypatch) -> None:
    config = foundry_client.FoundryConfig(
        project_endpoint="https://resource.services.ai.azure.com/api/projects/project",
        api_key="test-secret-key",
        model_name="vision-deployment",
        timeout_seconds=5,
        max_retries=1,
    )
    captured: dict[str, object] = {}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json={"output_text": "structured analysis placeholder"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(foundry_client.httpx, "post", fake_post)

    result = foundry_client.FoundryClient(config).analyze_text("Analyze this item.")

    assert result.output_text == "structured analysis placeholder"
    assert captured["url"].endswith("/openai/v1/responses")
    assert captured["json"] == {"model": "vision-deployment", "input": "Analyze this item."}
    assert captured["headers"] == {
        "api-key": "test-secret-key",
        "Content-Type": "application/json",
    }


def test_foundry_vision_response_is_parsed_and_normalized(monkeypatch) -> None:
    config = foundry_client.FoundryConfig(
        project_endpoint="https://resource.services.ai.azure.com/api/projects/project",
        api_key="test-secret-key",
        model_name="gpt-5-mini",
        timeout_seconds=5,
        max_retries=1,
    )
    captured: dict[str, object] = {}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"description": "Black insulated stainless steel water bottle.",'
                                ' "object_type": "water bottle", "category": "Personal Items",'
                                ' "primary_color": "black", "secondary_colors": ["silver"],'
                                ' "brand": "Hydro Flask", "visible_features": ["scratches on base"],'
                                ' "visible_text": ["Hydro Flask"], "confidence": 0.95}'
                            )
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(foundry_client.httpx, "post", fake_post)

    result = foundry_client.FoundryClient(config).analyze_image(
        b"\x89PNG\r\n\x1a\nfakeimage",
        mime_type="image/png",
    )

    assert result.description == "Black insulated stainless steel water bottle."
    assert result.attributes["object_type"] == "water bottle"
    assert result.attributes["category"] == "Personal Items"
    assert result.attributes["primary_color"] == "black"
    assert result.attributes["brand"] == "Hydro Flask"
    assert result.attributes["visible_features"] == ["scratches on base"]
    assert result.attributes["visible_text"] == ["Hydro Flask"]
    assert result.attributes["confidence"] == 0.95
    assert str(captured["url"]).endswith("/openai/v1/chat/completions")
    assert captured["headers"] == {
        "api-key": "test-secret-key",
        "Content-Type": "application/json",
    }


def test_foundry_vision_failures_are_safe_and_retry_bounded(monkeypatch) -> None:
    config = foundry_client.FoundryConfig(
        project_endpoint="https://resource.services.ai.azure.com/api/projects/project",
        api_key="test-secret-key",
        model_name="gpt-5-mini",
        timeout_seconds=5,
        max_retries=2,
    )
    attempts = 0

    def fail_post(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("private network detail")

    monkeypatch.setattr(foundry_client.httpx, "post", fail_post)

    with pytest.raises(foundry_client.FoundryServiceError) as error:
        foundry_client.FoundryClient(config).analyze_image(b"\x89PNG\r\n\x1a\nfakeimage")

    assert attempts == 3
    assert str(error.value) == "Microsoft Foundry vision request failed."
    assert "private network detail" not in str(error.value)
    assert "test-secret-key" not in str(error.value)
