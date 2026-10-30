"""Correct the confirmed Supertubos location description with provenance.

Revision ID: 0092_fix_supertubos
Revises: 0091_decision_support_gates
"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0092_fix_supertubos"
down_revision = "0091_decision_support_gates"
branch_labels = None
depends_on = None

SPOT_ID = "c24cca3c-3cf1-4bf9-af59-9453b7264265"
SLUG = "peniche-supertubos"
SOURCE_URL = "https://www.visitportugal.com/en/content/surfing-and-bodyboarding"
OLD_DESCRIPTION = (
    "Das weitläufige Küstenrevier im Osten der Algarve zeichnet sich durch lange Sandstrände, geschützte Lagunen und vergleichsweise ruhige Wasserbedingungen aus. "
    "Durch die vorgelagerten Inseln und Sandbänke der Ria Formosa entstehen vielerorts flache Bereiche, die sich besonders für entspannte Sessions und erste Erfahrungen auf dem Wasser eignen. "
    "Im Vergleich zur offenen Westküste Portugals erreicht deutlich weniger Atlantikswell die Region, sodass große und kraftvolle Wellen eher selten sind. "
    "Bei stärkerem Wind können außerhalb der geschützten Bereiche dennoch Chop und kleinere Windwellen entstehen, die abwechslungsreiche Bedingungen bieten. "
    "Die weitläufigen Strände rund um Tavira, Cabanas, Manta Rota und Monte Gordo bieten viel Platz und meist unkomplizierte Einstiege über Sand. "
    "Durch die geringe Wassertiefe in einigen Bereichen verändern Tide und Sandbänke die Bedingungen teilweise deutlich. "
    "Besonders im Sommer sorgen warmes Wasser und eine gut ausgebaute touristische Infrastruktur für angenehme Bedingungen rund um die Session. "
    "Insgesamt steht das Revier weniger für anspruchsvolle Atlantikwellen als für entspanntes Flachwasser, breite Sandstrände und den ruhigen Charakter der östlichen Algarve."
)
NEW_DESCRIPTION = (
    "Supertubos, auch Praia do Medão, liegt bei Peniche. Der Strand ist für ausgeprägte Tubewellen bekannt, bei Surfern aus aller Welt beliebt und Austragungsort einer Veranstaltung der World Surf League. "
    "Welche Bedingungen vor Ort tatsächlich herrschen, hängt vom aktuellen Swell, Wind und Wasserstand ab."
)


def upgrade() -> None:
    connection = op.get_bind()
    changed = connection.execute(sa.text("""
        UPDATE spots
        SET editorial = jsonb_set(COALESCE(editorial, '{}'::jsonb), '{description}', to_jsonb(CAST(:new_description AS text)), true),
            content_status = CASE WHEN content_status = 'conflict' THEN 'conflict' ELSE 'in_review' END,
            content_reviewed_at = NULL,
            content_reviewed_by = NULL,
            content_review_due_at = NULL,
            updated_at = now()
        WHERE id = CAST(:spot_id AS uuid)
          AND slug = :slug
          AND editorial->>'description' = :old_description
        RETURNING id
    """), {"spot_id": SPOT_ID, "slug": SLUG, "old_description": OLD_DESCRIPTION, "new_description": NEW_DESCRIPTION}).first()
    if changed is None:
        return
    connection.execute(sa.text("""
        INSERT INTO spot_content_sources (
            id, spot_id, field_path, url, title, publisher, checked_at,
            verification_status, note, created_by, reviewed_by, created_at, updated_at
        ) VALUES (
            gen_random_uuid(), CAST(:spot_id AS uuid), 'editorial.description', :url,
            'Surfing and bodyboarding', 'Turismo de Portugal', :checked_at,
            'verified', 'Belegt Lage bei Peniche, Tubewellen und WSL-Veranstaltung.',
            'migration:0092', 'migration:0092', now(), now()
        )
        ON CONFLICT (spot_id, field_path, url) DO UPDATE SET
            title = EXCLUDED.title, publisher = EXCLUDED.publisher,
            checked_at = EXCLUDED.checked_at, verification_status = 'verified',
            note = EXCLUDED.note, reviewed_by = EXCLUDED.reviewed_by, updated_at = now()
    """), {"spot_id": SPOT_ID, "url": SOURCE_URL, "checked_at": datetime(2026, 10, 30, 12, tzinfo=timezone.utc)})


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("""
        DELETE FROM spot_content_sources
        WHERE spot_id = CAST(:spot_id AS uuid)
          AND field_path = 'editorial.description'
          AND url = :url
          AND created_by = 'migration:0092'
    """), {"spot_id": SPOT_ID, "url": SOURCE_URL})
    connection.execute(sa.text("""
        UPDATE spots
        SET editorial = jsonb_set(COALESCE(editorial, '{}'::jsonb), '{description}', to_jsonb(CAST(:old_description AS text)), true),
            content_status = 'unreviewed', updated_at = now()
        WHERE id = CAST(:spot_id AS uuid)
          AND slug = :slug
          AND editorial->>'description' = :new_description
    """), {"spot_id": SPOT_ID, "slug": SLUG, "old_description": OLD_DESCRIPTION, "new_description": NEW_DESCRIPTION})
