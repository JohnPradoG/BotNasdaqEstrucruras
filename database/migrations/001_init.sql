-- 001: esquema inicial de la memoria histórica
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id   TEXT PRIMARY KEY,         -- hash del conjunto M1
    symbol       TEXT NOT NULL,
    provider     TEXT NOT NULL,
    start_time   TEXT NOT NULL,
    end_time     TEXT NOT NULL,
    rows         INTEGER NOT NULL,
    quality_json TEXT,
    created_at   TEXT NOT NULL
);

-- Nivel 1: episodios (TODAS las estructuras válidas, operadas o no)
CREATE TABLE IF NOT EXISTS episodes (
    episode_id     TEXT PRIMARY KEY,       -- hash(símbolo, tf, tipo, dirección, instante)
    dataset_id     TEXT REFERENCES datasets(dataset_id),
    params_hash    TEXT NOT NULL,          -- parámetros de los detectores
    symbol         TEXT NOT NULL,
    tf             TEXT NOT NULL,          -- temporalidad de la estructura
    context_tfs    TEXT NOT NULL,          -- p. ej. "H4,H1"
    structure_type TEXT NOT NULL,
    direction      INTEGER NOT NULL,       -- +1 alcista, -1 bajista
    origin         TEXT,                   -- bos/choch para retesteos y falsas rupturas
    bar_index      INTEGER NOT NULL,
    detected_time  TEXT NOT NULL,          -- instante en que la estructura pasa a ser conocida (cierre de vela)
    level          REAL, extreme REAL, protective REAL,
    entry_ref      REAL,                   -- cierre de la vela de detección
    invalidation   REAL,                   -- nivel de invalidación usado para el R
    atr            REAL, spread_points REAL, session TEXT,
    trend_tf       INTEGER, trend_ctx1 INTEGER, trend_ctx2 INTEGER,
    features_json  TEXT NOT NULL,          -- características normalizadas (solo info pasada)
    confirmations_json TEXT,
    data_quality   TEXT
);
CREATE INDEX IF NOT EXISTS ix_ep_type_time ON episodes(structure_type, tf, detected_time);

-- Nivel 2: desenlaces (se conocen en matured_time; nunca antes)
CREATE TABLE IF NOT EXISTS outcomes (
    episode_id    TEXT PRIMARY KEY REFERENCES episodes(episode_id),
    status        TEXT NOT NULL,           -- ok | sin_datos | geometria_invalida
    entry_time    TEXT, entry_price REAL, risk_price REAL, risk_atr REAL,
    matured_time  TEXT,                    -- instante en que se conoce el desenlace completo
    mfe_r REAL, mae_r REAL, mfe_atr REAL, mae_atr REAL,
    duration_min  INTEGER,
    res_1r REAL, res_1_5r REAL, res_2r REAL, res_time REAL,   -- resultado neto en R de cada salida hipotética
    exit_reason_2r TEXT,
    cost_r        REAL                     -- spread + deslizamiento expresado en R
);

-- Nivel 3: estadísticas agregadas
CREATE TABLE IF NOT EXISTS aggregates (
    agg_key     TEXT PRIMARY KEY,          -- tipo|tf|dirección|sesión|vol|contexto
    structure_type TEXT, tf TEXT, direction INTEGER, session TEXT, vol_bucket TEXT, context TEXT,
    period      TEXT,                      -- periodo de datos usado
    n INTEGER, n_eff INTEGER, hit_2r REAL, hit_2r_lo REAL, hit_2r_hi REAL,
    exp_r REAL, exp_r_lo REAL, exp_r_hi REAL, median_mae_r REAL, median_mfe_r REAL,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS model_versions (
    version_id   TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,
    parent_id    TEXT,
    params_json  TEXT NOT NULL,
    train_end    TEXT NOT NULL,
    metrics_json TEXT,
    status       TEXT NOT NULL             -- candidate | active | rejected | retired
);

CREATE TABLE IF NOT EXISTS experiments (
    run_id       TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,
    code_version TEXT, config_json TEXT, seed INTEGER, results_path TEXT, summary_json TEXT
);

CREATE TABLE IF NOT EXISTS execution_journal (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    mode        TEXT NOT NULL,             -- paper | demo
    client_id   TEXT NOT NULL,             -- id idempotente de la señal
    kind        TEXT NOT NULL,             -- request | response | reconcile | block
    payload_json TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_journal_request ON execution_journal(client_id, kind) WHERE kind = 'request';
