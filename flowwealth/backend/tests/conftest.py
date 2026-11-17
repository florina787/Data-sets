import pytest

from flowwealth.data.lake import DataLake, attach_timestamps
from flowwealth.data.providers.synthetic import generate_universe
from flowwealth.data.quality import clean_bars


@pytest.fixture(scope="session")
def small_universe():
    raw, master, meta = generate_universe(60, "2020-01-01", "2022-12-31", seed=3)
    return raw, master, meta


@pytest.fixture(scope="session")
def clean_small(small_universe):
    raw, master, meta = small_universe
    clean, rep = clean_bars(raw)
    return attach_timestamps(clean), master, rep


@pytest.fixture(scope="session")
def lake(tmp_path_factory, clean_small):
    bars, master, rep = clean_small
    lk = DataLake(tmp_path_factory.mktemp("lake"))
    lk.write_version("t1", bars, master, rep.to_dict(), {"source": "test"})
    return lk
