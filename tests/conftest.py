import pytest

from journeylab.config import GeneratorConfig
from journeylab.evaluate import evaluate
from journeylab.generate import build
from journeylab.validate import validate

TEST_SCALE = 0.02          # 2,000 sessions: same generator, small and fast
TEST_SEED = 20261022


@pytest.fixture(scope="session")
def cfg():
    return GeneratorConfig(seed=TEST_SEED, scale=TEST_SCALE)


@pytest.fixture(scope="session")
def ds(cfg):
    return build(cfg, log=lambda *_: None)


@pytest.fixture(scope="session")
def report(ds):
    return validate(ds.tables, ds.truth)


@pytest.fixture(scope="session")
def ev_report(ds):
    return evaluate(ds.tables, ds.truth, ds.derived, ds.expected_findings)
