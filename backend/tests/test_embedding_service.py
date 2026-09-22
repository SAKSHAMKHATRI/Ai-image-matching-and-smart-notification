import json
import math
from unittest.mock import MagicMock, patch

import pytest
from app.services.embedding_service import (
    EmbeddingFailed,
    EmbeddingResult,
    EmbeddingUnavailable,
    FoundryEmbeddingProvider,
    UnavailableEmbeddingProvider,
    cosine_similarity,
    deserialize_embedding,
    get_embedding_provider,
    serialize_embedding,
)
from app.services.foundry_client import (
    FoundryConfig,
    FoundryConfigurationError,
    FoundryServiceError,
    FoundryVisionResult,
)


@pytest.fixture
def mock_foundry_config():
    return FoundryConfig(
        project_endpoint="https://test.services.ai.azure.com/api/projects/test",
        api_key="test-key",
        model_name="gpt-5-mini",
        embedding_model_name="text-embedding-3-small",
        timeout_seconds=5.0,
        max_retries=1,
    )


@pytest.fixture
def mock_foundry_client(mock_foundry_config):
    client = MagicMock()
    client.config = mock_foundry_config
    return client


def test_serialize_and_deserialize_embedding():
    vector = [0.1, -0.2, 0.5, 0.99]
    serialized = serialize_embedding(vector)
    assert isinstance(serialized, str)
    parsed = json.loads(serialized)
    assert parsed == vector

    deserialized = deserialize_embedding(serialized)
    assert deserialized == vector

    assert serialize_embedding(None) is None
    assert deserialize_embedding(None) is None
    assert deserialize_embedding("") is None
    assert deserialize_embedding("invalid json") is None


def test_serialize_embedding_validation():
    with pytest.raises(ValueError):
        serialize_embedding("not a list")  # type: ignore[arg-type]


def test_cosine_similarity_math():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v2), abs=1e-4) == 1.0

    v3 = [0.0, 1.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v3), abs=1e-4) == 0.0

    v4 = [-1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v4), abs=1e-4) == -1.0

    assert cosine_similarity(None, v1) == 0.0
    assert cosine_similarity(v1, None) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_embed_text_valid(mock_foundry_client):
    mock_vector = [0.01] * 1536
    mock_foundry_client.generate_embedding.return_value = mock_vector

    provider = FoundryEmbeddingProvider(client=mock_foundry_client)
    result = provider.embed_text("Lost black leather wallet near library")

    assert result.status == "SUCCESS"
    assert result.input_type == "text"
    assert result.model == "text-embedding-3-small"
    assert result.dimensions == 1536
    assert result.vector == mock_vector
    mock_foundry_client.generate_embedding.assert_called_once_with("Lost black leather wallet near library")


def test_embed_text_empty_input(mock_foundry_client):
    provider = FoundryEmbeddingProvider(client=mock_foundry_client)
    with pytest.raises(ValueError):
        provider.embed_text("   ")


def test_embed_text_provider_failure(mock_foundry_client):
    mock_foundry_client.generate_embedding.side_effect = FoundryServiceError("API Timeout")
    provider = FoundryEmbeddingProvider(client=mock_foundry_client)

    with pytest.raises(EmbeddingFailed):
        provider.embed_text("Blue hydroflask water bottle")


def test_embed_image_valid(mock_foundry_client):
    mock_vector = [0.02] * 1536
    mock_vision_res = FoundryVisionResult(
        description="Blue metal water bottle with sticker",
        attributes={
            "description": "Blue metal water bottle with sticker",
            "object_type": "water bottle",
            "category": "Personal Items",
            "primary_color": "Blue",
            "brand": "Hydro Flask",
            "visible_features": ["sticker"],
            "visible_text": ["Campus Sports"],
        },
        raw={},
    )

    mock_foundry_client.analyze_image.return_value = mock_vision_res
    mock_foundry_client.generate_embedding.return_value = mock_vector

    provider = FoundryEmbeddingProvider(client=mock_foundry_client)
    fake_image_bytes = b"\xff\xd8\xff\xe0"

    result = provider.embed_image(fake_image_bytes, mime_type="image/jpeg")

    assert result.status == "SUCCESS"
    assert result.input_type == "image"
    assert result.model == "text-embedding-3-small"
    assert result.dimensions == 1536
    assert result.vector == mock_vector

    mock_foundry_client.analyze_image.assert_called_once()
    mock_foundry_client.generate_embedding.assert_called_once()


def test_embed_image_vision_failure_with_fallback(mock_foundry_client):
    mock_vector = [0.03] * 1536
    mock_foundry_client.analyze_image.side_effect = Exception("Vision model error")
    mock_foundry_client.generate_embedding.return_value = mock_vector

    provider = FoundryEmbeddingProvider(client=mock_foundry_client)

    result = provider.embed_image(
        image_bytes=b"\xff\xd8\xff",
        fallback_text="Fallback description for lost keys",
    )

    assert result.status == "SUCCESS"
    assert result.vector == mock_vector
    mock_foundry_client.generate_embedding.assert_called_once_with("Fallback description for lost keys")


def test_embed_image_missing_all_inputs(mock_foundry_client):
    provider = FoundryEmbeddingProvider(client=mock_foundry_client)
    with pytest.raises(ValueError):
        provider.embed_image(b"", fallback_text=None)


def test_unavailable_embedding_provider():
    provider = UnavailableEmbeddingProvider()
    with pytest.raises(EmbeddingUnavailable):
        provider.embed_text("some text")
    with pytest.raises(EmbeddingUnavailable):
        provider.embed_image(b"fake image")


def test_get_embedding_provider_factory():
    with patch("app.services.embedding_service.get_foundry_client") as mock_get_client:
        mock_get_client.side_effect = FoundryConfigurationError("Missing endpoint")
        provider = get_embedding_provider()
        assert isinstance(provider, UnavailableEmbeddingProvider)


def test_generate_semantic_feature_vector():
    from app.services.embedding_service import generate_semantic_feature_vector

    # 1. Non-empty text produces unit-normalized 1536-dim vector
    vec1 = generate_semantic_feature_vector("Black backpack with HRX logo and zippers")
    assert len(vec1) == 1536
    norm1 = math.sqrt(sum(x * x for x in vec1))
    assert pytest.approx(norm1, abs=1e-4) == 1.0

    # 2. Similar descriptions produce non-zero, positive similarity
    vec2 = generate_semantic_feature_vector("hrx black bagpack with laptop inside")
    sim_same = cosine_similarity(vec1, vec2)
    assert sim_same > 0.20

    # 3. Unrelated descriptions produce significantly lower similarity
    vec3 = generate_semantic_feature_vector("Stainless steel silver water bottle")
    sim_diff = cosine_similarity(vec1, vec3)
    assert sim_same > sim_diff

    # 4. Empty/whitespace text returns all zeros
    vec_empty = generate_semantic_feature_vector("   ")
    assert len(vec_empty) == 1536
    assert all(x == 0.0 for x in vec_empty)
    assert cosine_similarity(vec_empty, vec1) == 0.0
