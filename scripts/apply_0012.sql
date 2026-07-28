-- Migration 0012: admin_notifications (operator dashboard badge)
-- Raw-SQL-Fallback, idempotent (IF NOT EXISTS) — im Neon SQL-Editor einfügen
-- und auf der PRODUKTIONS-Branch ausführen (dieselbe DB, die surfwinddata.com
-- UND das dashboard-Projekt nutzen).

CREATE TABLE IF NOT EXISTS admin_notifications (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type       varchar(40) NOT NULL,
    message    text        NOT NULL,
    spot_id    uuid REFERENCES spots(id) ON DELETE SET NULL,
    read_at    timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_admin_notifications_unread
    ON admin_notifications (read_at, created_at);
