"""Test-suite guardrails.

The one rule here: running the tests must not touch anything real.

That was not true, and it cost money. `finish_call` ends with

    settings = settings or Settings()

and `Settings()` reads `.env`. Every test that called `finish_call` without
passing settings therefore picked up the developer's live project and live
`SAMPAN_MEMORIES_TOPIC`, and `publish()` -- which is deliberately fire-and-
forget and deliberately never raises -- posted a real Pub/Sub message per
story. Each one pushed to the deployed service and rendered a real Veo clip.

Nothing failed. The tests passed, in under thirteen seconds, while roughly
twenty paid video generations ran in the background on every single run. It
was only visible from the outside: a storage bucket that had grown to eighty-
six objects, eighty of which were the same four seconds of a 1958 coffee shop.

The env vars are cleared for the whole session rather than patched per test,
because the hazard is not any one test -- it is that a helper three layers down
can reach the network from a config file nobody passed it.
"""

from __future__ import annotations

import pytest

# Anything that lets library code reach a real Google Cloud project. Cleared
# before the first test is collected, restored afterwards.
NEVER_IN_TESTS = (
    "SAMPAN_MEMORIES_TOPIC",
    "SAMPAN_MEMORIES_BUCKET",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "SAMPAN_ARMOR_TEMPLATE",
    "SAMPAN_DLP_INSPECT_TEMPLATE",
    "SAMPAN_DLP_DEIDENTIFY_TEMPLATE",
)


@pytest.fixture(autouse=True, scope="session")
def _no_live_services():
    """Make it impossible for a unit test to reach production.

    `autouse` and session-scoped: a test does not opt into this, and cannot
    opt out of it by forgetting.

    Integration tests are the deliberate exception and are deselected by
    default (`-m integration`); they build their own Settings and are expected
    to know what they are doing.
    """
    import os

    from sampan.config import Settings

    # Clearing the environment is not enough on its own, and finding that out
    # is the whole lesson here: `Settings` is configured with `env_file=".env"`,
    # so it reads the developer's file directly whether or not anything is
    # exported. The file read is what has to be switched off.
    held_env = {name: os.environ.pop(name, None) for name in NEVER_IN_TESTS}
    held_file = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None
    try:
        yield
    finally:
        Settings.model_config["env_file"] = held_file
        for name, value in held_env.items():
            if value is not None:
                os.environ[name] = value
