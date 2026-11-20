"""Nudges must always be answerable: every canonical suggestion routes to its analysis by a high-precision rule."""

import pytest

from app.agents.intent_router import route_intent
from app.agents.suggestions import CANONICAL, DEFAULT, suggest


@pytest.mark.parametrize("intent,question", sorted(CANONICAL.items()))
def test_every_suggestion_routes_to_its_analysis_by_rule(intent, question):
    r = route_intent(question, allow_llm=False)
    assert (r.label, r.method) == (intent, "rules")


def test_suggestions_are_answerable_and_bounded():
    out = suggest("what do you recommend we do first?")
    assert 1 <= len(out) <= 3 and set(out) <= set(CANONICAL.values()) | set(DEFAULT)
    assert len(set(out)) == len(out)
