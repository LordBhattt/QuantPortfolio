import uuid

import pytest


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.uuid4()
