"""Independent numeric-token regression, separate from prose privacy validation."""
import pytest

from agents.financial_close import generation


@pytest.mark.parametrize(
    'text,catalog,expected',
    [
        ('Verified actual is 48150.', {'48150'}, True),
        ('Verified actual is 111111.', {'1'}, False),
        ('Verified actual is -48150.', {'48150'}, False),
        ('Verified actual is 48150.1.', {'48150','1'}, False),
    ],
)
def test_numeric_grounding_requires_whole_supported_value(monkeypatch, text, catalog, expected):
    # Privacy has its own negative and positive tests. Isolate this numeric gate
    # so a failing prose detector cannot hide acceptance of fabricated amounts.
    monkeypatch.setattr(generation, 'is_safe_prose', lambda _: True)
    assert generation.text_is_grounded(text, catalog) is expected
