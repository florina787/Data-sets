-- FICTIONAL flat-file inventory staging schema (APP-06 -> APP-05). Parsed, never executed.
-- system: Flat-file Inventory (APP-06)
-- owner: Warehouse ops
-- batch_window: 01:00
-- last_reviewed: 2023-02-10

CREATE TABLE STG_INVENTORY_NIGHTLY (
  REC_TYPE      CHAR(2),
  PART_NO       VARCHAR(20),
  BASE_CODE     VARCHAR(12),
  QTY_COUNTED   INTEGER,
  LOT_NO        VARCHAR(20),
  COUNT_DATE    DATE,
  COUNTER_ID    VARCHAR(10)
);

CREATE TABLE STG_REJECTS (
  LINE_NO       INTEGER,
  RAW_LINE      VARCHAR(2000),
  REASON        VARCHAR(200)
);
