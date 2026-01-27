"""Tests for configuration management."""

import pytest

from buun_curator.config import (
    DEFAULT_DISTILLATION_BATCH_SIZE,
    DEFAULT_EMBEDDING_BACKFILL_BATCH_SIZE,
    DEFAULT_GLOBAL_GRAPH_UPDATE_BATCH_SIZE,
    DEFAULT_GRAPH_REBUILD_BATCH_SIZE,
    DEFAULT_SEARCH_PRUNE_BATCH_SIZE,
    DEFAULT_SEARCH_REINDEX_BATCH_SIZE,
    Config,
    get_env,
)
from buun_curator.models.workflow_io import (
    ContentDistillationInput,
    EmbeddingBackfillInput,
    GlobalGraphUpdateInput,
    GraphRebuildInput,
    ScheduleFetchInput,
    SearchPruneInput,
    SearchReindexInput,
    SingleFeedIngestionInput,
)

# =============================================================================
# get_env function tests
# =============================================================================


def test_get_env_returns_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_env returns the env var value when set."""
    monkeypatch.setenv("TEST_VAR", "test-value")
    assert get_env("TEST_VAR", "default") == "test-value"


def test_get_env_returns_default_when_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_env returns default when env var is not set."""
    monkeypatch.delenv("TEST_VAR", raising=False)
    assert get_env("TEST_VAR", "default-value") == "default-value"


def test_get_env_raises_when_required_and_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_env raises ValueError when required env var is not set."""
    monkeypatch.delenv("REQUIRED_VAR", raising=False)
    with pytest.raises(ValueError, match="Required environment variable 'REQUIRED_VAR' is not set"):
        get_env("REQUIRED_VAR", None)


def test_get_env_returns_value_when_required_and_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_env returns value when required env var is set."""
    monkeypatch.setenv("REQUIRED_VAR", "secret-value")
    assert get_env("REQUIRED_VAR", None) == "secret-value"


def test_get_env_empty_string_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_env can use empty string as default."""
    monkeypatch.delenv("OPTIONAL_VAR", raising=False)
    assert get_env("OPTIONAL_VAR", "") == ""


def test_config_raises_when_required_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Config.from_env raises when required env vars are missing."""
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="INTERNAL_API_TOKEN"):
        Config.from_env()


class TestDistillationBatchSize:
    """Tests for distillation_batch_size configuration."""

    def test_default_value_constant(self) -> None:
        """Verify DEFAULT_DISTILLATION_BATCH_SIZE is defined correctly."""
        assert DEFAULT_DISTILLATION_BATCH_SIZE == 5

    def test_from_env_uses_default_when_not_set(
        self, monkeypatch: pytest.MonkeyPatch, required_env_vars: None
    ) -> None:
        """Test that DEFAULT_DISTILLATION_BATCH_SIZE is used when env var is not set."""
        # Ensure the env var is not set
        monkeypatch.delenv("DISTILLATION_BATCH_SIZE", raising=False)

        config = Config.from_env()

        assert config.distillation_batch_size == DEFAULT_DISTILLATION_BATCH_SIZE

    def test_from_env_reads_env_var(
        self, monkeypatch: pytest.MonkeyPatch, required_env_vars: None
    ) -> None:
        """Test that DISTILLATION_BATCH_SIZE is read from environment."""
        monkeypatch.setenv("DISTILLATION_BATCH_SIZE", "10")

        config = Config.from_env()

        assert config.distillation_batch_size == 10

    def test_from_env_with_different_values(
        self, monkeypatch: pytest.MonkeyPatch, required_env_vars: None
    ) -> None:
        """Test various valid values for DISTILLATION_BATCH_SIZE."""
        test_cases = [1, 3, 20, 100]

        for value in test_cases:
            monkeypatch.setenv("DISTILLATION_BATCH_SIZE", str(value))
            config = Config.from_env()
            assert config.distillation_batch_size == value, f"Failed for value {value}"


class TestWorkflowInputDefaults:
    """Tests for workflow input model default values."""

    def test_content_distillation_input_default(self) -> None:
        """Test ContentDistillationInput uses DEFAULT_DISTILLATION_BATCH_SIZE."""
        input_model = ContentDistillationInput()
        assert input_model.batch_size == DEFAULT_DISTILLATION_BATCH_SIZE

    def test_schedule_fetch_input_default(self) -> None:
        """Test ScheduleFetchInput uses DEFAULT_DISTILLATION_BATCH_SIZE."""
        input_model = ScheduleFetchInput(entries=[])
        assert input_model.distillation_batch_size == DEFAULT_DISTILLATION_BATCH_SIZE

    def test_single_feed_ingestion_input_default(self) -> None:
        """Test SingleFeedIngestionInput uses DEFAULT_DISTILLATION_BATCH_SIZE."""
        input_model = SingleFeedIngestionInput(
            feed_id="test-feed",
            feed_name="Test Feed",
            feed_url="https://example.com/feed",
        )
        assert input_model.distillation_batch_size == DEFAULT_DISTILLATION_BATCH_SIZE

    def test_explicit_batch_size_overrides_default(self) -> None:
        """Test that explicit batch_size overrides the default."""
        input_model = ContentDistillationInput(batch_size=10)
        assert input_model.batch_size == 10

        schedule_input = ScheduleFetchInput(entries=[], distillation_batch_size=20)
        assert schedule_input.distillation_batch_size == 20


class TestAdminBatchSizeDefaults:
    """Tests for admin workflow batch size default constants."""

    def test_default_values(self) -> None:
        """Verify all admin batch size defaults are defined correctly."""
        assert DEFAULT_SEARCH_REINDEX_BATCH_SIZE == 500
        assert DEFAULT_SEARCH_PRUNE_BATCH_SIZE == 1000
        assert DEFAULT_GRAPH_REBUILD_BATCH_SIZE == 50
        assert DEFAULT_GLOBAL_GRAPH_UPDATE_BATCH_SIZE == 50
        assert DEFAULT_EMBEDDING_BACKFILL_BATCH_SIZE == 100

    def test_config_uses_defaults_when_not_set(
        self, monkeypatch: pytest.MonkeyPatch, required_env_vars: None
    ) -> None:
        """Test that default values are used when env vars are not set."""
        # Remove all batch size env vars
        for env_var in [
            "SEARCH_REINDEX_BATCH_SIZE",
            "SEARCH_PRUNE_BATCH_SIZE",
            "GRAPH_REBUILD_BATCH_SIZE",
            "GLOBAL_GRAPH_UPDATE_BATCH_SIZE",
            "EMBEDDING_BACKFILL_BATCH_SIZE",
        ]:
            monkeypatch.delenv(env_var, raising=False)

        config = Config.from_env()

        assert config.search_reindex_batch_size == DEFAULT_SEARCH_REINDEX_BATCH_SIZE
        assert config.search_prune_batch_size == DEFAULT_SEARCH_PRUNE_BATCH_SIZE
        assert config.graph_rebuild_batch_size == DEFAULT_GRAPH_REBUILD_BATCH_SIZE
        assert config.global_graph_update_batch_size == DEFAULT_GLOBAL_GRAPH_UPDATE_BATCH_SIZE
        assert config.embedding_backfill_batch_size == DEFAULT_EMBEDDING_BACKFILL_BATCH_SIZE

    def test_config_reads_env_vars(
        self, monkeypatch: pytest.MonkeyPatch, required_env_vars: None
    ) -> None:
        """Test that batch sizes are read from environment variables."""
        monkeypatch.setenv("SEARCH_REINDEX_BATCH_SIZE", "1000")
        monkeypatch.setenv("SEARCH_PRUNE_BATCH_SIZE", "2000")
        monkeypatch.setenv("GRAPH_REBUILD_BATCH_SIZE", "100")
        monkeypatch.setenv("GLOBAL_GRAPH_UPDATE_BATCH_SIZE", "75")
        monkeypatch.setenv("EMBEDDING_BACKFILL_BATCH_SIZE", "200")

        config = Config.from_env()

        assert config.search_reindex_batch_size == 1000
        assert config.search_prune_batch_size == 2000
        assert config.graph_rebuild_batch_size == 100
        assert config.global_graph_update_batch_size == 75
        assert config.embedding_backfill_batch_size == 200


class TestAdminWorkflowInputDefaults:
    """Tests for admin workflow input model default values."""

    def test_search_reindex_input_default(self) -> None:
        """Test SearchReindexInput uses DEFAULT_SEARCH_REINDEX_BATCH_SIZE."""
        input_model = SearchReindexInput()
        assert input_model.batch_size == DEFAULT_SEARCH_REINDEX_BATCH_SIZE

    def test_search_prune_input_default(self) -> None:
        """Test SearchPruneInput uses DEFAULT_SEARCH_PRUNE_BATCH_SIZE."""
        input_model = SearchPruneInput()
        assert input_model.batch_size == DEFAULT_SEARCH_PRUNE_BATCH_SIZE

    def test_graph_rebuild_input_default(self) -> None:
        """Test GraphRebuildInput uses DEFAULT_GRAPH_REBUILD_BATCH_SIZE."""
        input_model = GraphRebuildInput()
        assert input_model.batch_size == DEFAULT_GRAPH_REBUILD_BATCH_SIZE

    def test_global_graph_update_input_default(self) -> None:
        """Test GlobalGraphUpdateInput uses DEFAULT_GLOBAL_GRAPH_UPDATE_BATCH_SIZE."""
        input_model = GlobalGraphUpdateInput()
        assert input_model.batch_size == DEFAULT_GLOBAL_GRAPH_UPDATE_BATCH_SIZE

    def test_embedding_backfill_input_default(self) -> None:
        """Test EmbeddingBackfillInput uses DEFAULT_EMBEDDING_BACKFILL_BATCH_SIZE."""
        input_model = EmbeddingBackfillInput()
        assert input_model.batch_size == DEFAULT_EMBEDDING_BACKFILL_BATCH_SIZE

    def test_explicit_batch_size_overrides_default(self) -> None:
        """Test that explicit batch_size overrides the default."""
        assert SearchReindexInput(batch_size=999).batch_size == 999
        assert SearchPruneInput(batch_size=888).batch_size == 888
        assert GraphRebuildInput(batch_size=77).batch_size == 77
        assert GlobalGraphUpdateInput(batch_size=66).batch_size == 66
        assert EmbeddingBackfillInput(batch_size=55).batch_size == 55


# =============================================================================
# CLI argument vs config priority tests
#
# The pattern used in trigger_workflow.py and schedule.py:
#     batch_size = args.batch_size if args.batch_size is not None else config.xxx
#
# This ensures:
# - None (not specified) → use config value
# - 0 (explicitly specified) → use 0
# - Any positive value → use that value
# =============================================================================


def test_batch_size_none_uses_config_value() -> None:
    """When args.batch_size is None, config value should be used."""
    args_batch_size = None
    config_value = 500

    result = args_batch_size if args_batch_size is not None else config_value

    assert result == config_value


def test_batch_size_zero_is_respected() -> None:
    """When args.batch_size is 0, 0 should be used (not config value).

    This is the key difference from using `or` which would treat 0 as falsy.
    """
    args_batch_size = 0
    config_value = 500

    result = args_batch_size if args_batch_size is not None else config_value

    assert result == 0
    assert result != config_value


def test_batch_size_positive_value_is_respected() -> None:
    """When args.batch_size is a positive value, that value should be used."""
    args_batch_size = 100
    config_value = 500

    result = args_batch_size if args_batch_size is not None else config_value

    assert result == 100


def test_batch_size_or_pattern_would_fail_with_zero() -> None:
    """Demonstrate why `or` pattern is wrong for this use case.

    This test documents the bug that was fixed.
    """
    args_batch_size = 0
    config_value = 500

    # The buggy pattern using `or`
    buggy_result = args_batch_size or config_value

    # This would incorrectly use config_value because 0 is falsy
    assert buggy_result == config_value  # Bug: user specified 0 but got 500

    # The correct pattern using explicit None check
    correct_result = args_batch_size if args_batch_size is not None else config_value

    assert correct_result == 0  # Correct: user specified 0 and got 0
