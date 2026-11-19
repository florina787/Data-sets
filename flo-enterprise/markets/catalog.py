"""Dataset catalog: provenance and licensing records for every market dataset FLO may use.

A dataset is usable for research only when ``approved_for_research`` is True. Approval records *why* and under which
restrictions. The licence shown on Kaggle is asserted by the uploader; upstream terms are recorded separately because
a Kaggle "CC0" label cannot relicense data the uploader did not own.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DatasetRecord:
    dataset_id: str
    kaggle_ref: str
    url: str
    title: str
    publisher: str
    kaggle_license: str
    upstream_source: str
    kaggle_version: int
    last_updated: str
    coverage: str
    markets: str
    adjustment: str
    timestamps: str
    approved_for_research: bool
    use_restrictions: str
    known_limitations: list[str] = field(default_factory=list)
    classification: str = "public"
    synthetic: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


CATALOG: dict[str, DatasetRecord] = {d.dataset_id: d for d in [
    DatasetRecord(
        dataset_id="kaggle-us-stocks-etfs-v3",
        kaggle_ref="borismarjanovic/price-volume-data-for-all-us-stocks-etfs",
        url="https://www.kaggle.com/datasets/borismarjanovic/price-volume-data-for-all-us-stocks-etfs",
        title="Huge Stock Market Dataset (all U.S. stocks and ETFs)", publisher="Boris Marjanovic",
        kaggle_license="CC0: Public Domain", upstream_source="Not stated by the uploader (\"This dataset belongs to me\")",
        kaggle_version=3, last_updated="2017-11-16",
        coverage="Daily, 1962-01-02 to 2017-11-10 (most series much shorter); research window 2005-02-25 to 2017-11-10",
        markets="NYSE, NASDAQ, NYSE MKT stocks and ETFs",
        adjustment="Prices adjusted for splits and dividends by the uploader (back-adjusted); no raw prices",
        timestamps="Trade date only; FLO assumes availability at 16:30 America/New_York on that date",
        approved_for_research=True,
        use_restrictions="Research and education inside FLO. Do not redistribute the data; upstream terms are unknown.",
        known_limitations=[
            "SURVIVORSHIP BIAS: every stock series reaches 2017 (no series ends before 2017-01-01); companies that delisted earlier are absent",
            "Back-adjusted price levels embed later dividends and splits; only returns and volume-based features are used",
            "SPY history in this dataset starts 2005-02-25, which bounds the benchmark window",
            "The archive ships a byte-identical duplicate copy under Data/; ingestion deduplicates it by checksum",
            "32 empty stock files",
        ]),
    DatasetRecord(
        dataset_id="kaggle-nyse-sp500-v3", kaggle_ref="dgawlik/nyse", url="https://www.kaggle.com/datasets/dgawlik/nyse",
        title="New York Stock Exchange (S&P 500 prices and fundamentals)", publisher="Dominik Gawlik",
        kaggle_license="CC0: Public Domain", upstream_source="Prices from Yahoo Finance; fundamentals from annual SEC 10-K filings (per the description)",
        kaggle_version=3, last_updated="2017-02-22",
        coverage="Daily 2010-01-04 to 2016-12-30; fundamentals fiscal years 2012-2016", markets="501 S&P 500 constituents (2016 list)",
        adjustment="prices.csv raw; prices-split-adjusted.csv split-adjusted only (no dividends)",
        timestamps="Trade date; fundamentals carry period end only (no filing date)",
        approved_for_research=True,
        use_restrictions="Research and education; Yahoo-derived prices may not be redistributed commercially.",
        known_limitations=[
            "Constituent list is a 2016 snapshot (survivorship bias)",
            "Fundamentals have no filing/acceptance date, so they are NOT used in point-in-time signals",
            "Used for cross-source validation, split detection and sector labels (GICS)",
        ]),
    DatasetRecord(
        dataset_id="kaggle-benzinga-headlines-v2", kaggle_ref="miguelaenlle/massive-stock-news-analysis-db-for-nlpbacktests",
        url="https://www.kaggle.com/datasets/miguelaenlle/massive-stock-news-analysis-db-for-nlpbacktests",
        title="Daily Financial News for 6000+ Stocks", publisher="Miguel Aenlle",
        kaggle_license="CC0: Public Domain", upstream_source="Headlines scraped from Benzinga (and partner sites)",
        kaggle_version=2, last_updated="2020-07-04",
        coverage="2009-2020 headlines", markets="US-listed stocks (ticker-tagged)", adjustment="n/a",
        timestamps="raw_analyst_ratings.csv: publication time with UTC offset; partner headlines: date only",
        approved_for_research=True,
        use_restrictions="Headlines only, as cited research evidence inside FLO; no redistribution (publisher copyright likely applies).",
        known_limitations=[
            "Single publisher family (Benzinga); not comprehensive news coverage",
            "Partner headlines have no time of day and are excluded from point-in-time use",
            "Headlines are untrusted text and are scanned for prompt injection before use",
        ]),
    DatasetRecord(
        dataset_id="kaggle-nasdaq-yfinance-v2", kaggle_ref="jacksoncrow/stock-market-dataset",
        url="https://www.kaggle.com/datasets/jacksoncrow/stock-market-dataset", title="Stock Market Dataset", publisher="Oleh Onyshchak",
        kaggle_license="CC0: Public Domain", upstream_source="Yahoo Finance via yfinance", kaggle_version=2, last_updated="2020-04-02",
        coverage="Daily to 2020-04-01", markets="Tickers trading on NASDAQ in 2020", adjustment="Close split-adjusted; Adj Close also dividend-adjusted",
        timestamps="Trade date", approved_for_research=False,
        use_restrictions="Not ingested: overlaps the primary dataset, adds 2.7 GB, same survivorship bias (2020 listing snapshot).",
        known_limitations=["Survivorship bias: only tickers listed in 2020", "Yahoo terms restrict commercial reuse"]),
]}

PRIMARY = "kaggle-us-stocks-etfs-v3"
SECONDARY = "kaggle-nyse-sp500-v3"
NEWS = "kaggle-benzinga-headlines-v2"


def approved() -> list[DatasetRecord]:
    return [d for d in CATALOG.values() if d.approved_for_research]


def assert_real(record: DatasetRecord) -> None:
    """Research code calls this before using a dataset: synthetic or unapproved data never enters research."""
    if record.synthetic:
        raise ValueError(f"{record.dataset_id} is synthetic and may not be used for financial research")
    if not record.approved_for_research:
        raise ValueError(f"{record.dataset_id} is not approved for research: {record.use_restrictions}")
