import pytest

from busirag.config.validation import validate_embedding_configuration
from busirag.errors import ConfigurationError
from busirag.versioning import EMBEDDING_MODEL


def test_matching_embedding_model_is_valid():
    validate_embedding_configuration(EMBEDDING_MODEL)


def test_mismatched_embedding_model_is_rejected():
    with pytest.raises(ConfigurationError, match="does not match"):
        validate_embedding_configuration("some-other-embedding-model")