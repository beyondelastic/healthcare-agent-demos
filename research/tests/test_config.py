import pytest

from research_demo.config import require_configuration


@pytest.mark.parametrize("value", ["", "https://YOUR-ACCOUNT.example"])
def test_missing_or_template_configuration_fails_explicitly(value):
    with pytest.raises(ValueError, match="FOUNDRY_PROJECT_ENDPOINT"):
        require_configuration(FOUNDRY_PROJECT_ENDPOINT=value)


def test_supplied_configuration_is_accepted():
    require_configuration(FOUNDRY_PROJECT_ENDPOINT="https://example.services.ai.azure.com")
