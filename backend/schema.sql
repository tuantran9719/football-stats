-- =====================================================================
-- Lược đồ cơ sở dữ liệu PostgreSQL
--
-- Nguyên tắc thiết kế:
--   1. Dữ liệu thô từ nguồn được lưu nguyên vẹn ở bảng sự kiện, mọi con số
--      hiển thị đều tính lại được từ đó.
--   2. Cột phạt góc theo hiệp để sẵn nhưng cho phép NULL. NULL nghĩa là
--      không có dữ liệu, khác hẳn giá trị 0. Khi đổi sang nguồn trả phí có
--      mốc phút cho phạt góc thì chỉ việc đổ dữ liệu vào, không phải sửa bảng.
--   3. Mã định danh của nhà cung cấp tách riêng, để đổi nguồn không phải
--      đánh lại toàn bộ khóa chính.
-- =====================================================================

CREATE TABLE leagues (
  id          BIGSERIAL PRIMARY KEY,
  code        TEXT NOT NULL UNIQUE,      -- EPL, LALIGA, SERIEA, UCL
  name        TEXT NOT NULL,
  country     TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE teams (
  id          BIGSERIAL PRIMARY KEY,
  name        TEXT NOT NULL,
  short_name  TEXT,
  logo_url    TEXT,
  country     TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ánh xạ thực thể nội bộ sang mã của từng nhà cung cấp.
-- Nhờ bảng này mà thêm nguồn mới không cần đụng vào teams hay matches.
CREATE TABLE provider_refs (
  id           BIGSERIAL PRIMARY KEY,
  provider     TEXT NOT NULL,            -- espn, api-football, football-data-uk
  entity_type  TEXT NOT NULL,            -- team, league, match
  entity_id    BIGINT NOT NULL,
  external_id  TEXT NOT NULL,
  UNIQUE (provider, entity_type, external_id)
);
CREATE INDEX idx_provider_refs_entity ON provider_refs (entity_type, entity_id);

CREATE TABLE matches (
  id               BIGSERIAL PRIMARY KEY,
  league_id        BIGINT NOT NULL REFERENCES leagues(id),
  season           TEXT NOT NULL,
  kickoff_utc      TIMESTAMPTZ NOT NULL,
  status           TEXT NOT NULL,        -- scheduled, live, halftime, finished, postponed, cancelled
  home_team_id     BIGINT NOT NULL REFERENCES teams(id),
  away_team_id     BIGINT NOT NULL REFERENCES teams(id),
  home_score       SMALLINT,
  away_score       SMALLINT,
  ht_home_score    SMALLINT,
  ht_away_score    SMALLINT,
  source           TEXT NOT NULL,
  synced_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (league_id, season, home_team_id, away_team_id, kickoff_utc)
);
CREATE INDEX idx_matches_league_time ON matches (league_id, kickoff_utc DESC);
CREATE INDEX idx_matches_home ON matches (home_team_id, kickoff_utc DESC);
CREATE INDEX idx_matches_away ON matches (away_team_id, kickoff_utc DESC);

-- Sự kiện có mốc phút. Đây là nguồn sự thật để tách số liệu theo hiệp.
CREATE TABLE match_events (
  id            BIGSERIAL PRIMARY KEY,
  match_id      BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  minute        SMALLINT NOT NULL,
  extra_minute  SMALLINT,
  period        TEXT NOT NULL,           -- first, second, et1, et2
  event_type    TEXT NOT NULL,           -- goal, own_goal, yellow_card, red_card, ...
  side          TEXT NOT NULL,           -- home, away
  player_name   TEXT,
  description   TEXT
);
CREATE INDEX idx_events_match ON match_events (match_id, minute);

-- Thống kê cả trận lấy thẳng từ nguồn.
CREATE TABLE match_team_stats (
  match_id         BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  side             TEXT NOT NULL,        -- home, away
  corners          SMALLINT,
  shots            SMALLINT,
  shots_on_target  SMALLINT,
  fouls            SMALLINT,
  offsides         SMALLINT,
  possession_pct   NUMERIC(5,2),
  yellow_cards     SMALLINT,
  red_cards        SMALLINT,
  PRIMARY KEY (match_id, side)
);

-- Bảng tính sẵn theo hiệp, để màn hình chi tiết mở tức thì.
-- Cột phạt góc theo hiệp để NULL cho tới khi có nguồn cung cấp được.
CREATE TABLE match_split_stats (
  match_id            BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  side                TEXT NOT NULL,
  goals_first         SMALLINT NOT NULL DEFAULT 0,
  goals_second        SMALLINT NOT NULL DEFAULT 0,
  goals_full          SMALLINT NOT NULL DEFAULT 0,
  yellow_first        SMALLINT NOT NULL DEFAULT 0,
  yellow_second       SMALLINT NOT NULL DEFAULT 0,
  yellow_full         SMALLINT NOT NULL DEFAULT 0,
  red_first           SMALLINT NOT NULL DEFAULT 0,
  red_second          SMALLINT NOT NULL DEFAULT 0,
  red_full            SMALLINT NOT NULL DEFAULT 0,
  corners_first       SMALLINT,          -- NULL = không có dữ liệu, không phải 0
  corners_second      SMALLINT,          -- NULL = không có dữ liệu, không phải 0
  corners_full        SMALLINT,
  computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (match_id, side)
);

-- Tổng hợp đối đầu tính sẵn theo cửa sổ 5, 10, 20 trận.
CREATE TABLE h2h_summary (
  id              BIGSERIAL PRIMARY KEY,
  team_a_id       BIGINT NOT NULL REFERENCES teams(id),
  team_b_id       BIGINT NOT NULL REFERENCES teams(id),
  window_size     SMALLINT NOT NULL CHECK (window_size IN (5, 10, 20)),
  match_count     SMALLINT NOT NULL,
  payload         JSONB NOT NULL,        -- toàn bộ chỉ số đã tính, theo mô hình AggregatedStats
  computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (team_a_id, team_b_id, window_size)
);

-- Nhật ký đồng bộ, để biết nguồn nào hỏng lúc nào và tốn bao nhiêu request.
CREATE TABLE sync_log (
  id            BIGSERIAL PRIMARY KEY,
  provider      TEXT NOT NULL,
  job           TEXT NOT NULL,
  league_code   TEXT,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ,
  requests_used INT NOT NULL DEFAULT 0,
  rows_written  INT NOT NULL DEFAULT 0,
  status        TEXT NOT NULL DEFAULT 'running',  -- running, ok, failed
  error         TEXT
);
CREATE INDEX idx_sync_log_time ON sync_log (provider, started_at DESC);
