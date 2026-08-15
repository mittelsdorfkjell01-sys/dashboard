"""treat Wavekite as a derived riding style

Revision ID: 0037_wavekite_riding_style
Revises: 0036_weather_shadow_study
"""

from alembic import op

revision = "0037_wavekite_riding_style"
down_revision = "0036_weather_shadow_study"
branch_labels = None
depends_on = None


def upgrade():
    # Existing spots are normalized from their real sports. The style is added
    # only where both prerequisites exist and removed everywhere else.
    op.execute("""
        UPDATE spots
        SET sports = array_remove(sports, 'wavekite'),
            style = CASE
                WHEN sports @> ARRAY['kitesurf']::varchar[]
                 AND sports @> ARRAY['surf']::varchar[] THEN
                    array_append(array_remove(style, 'wavekite'), 'wavekite')
                ELSE array_remove(style, 'wavekite')
            END
    """)
    op.execute("UPDATE spot_ratings SET sport = 'kitesurf' WHERE sport = 'wavekite'")
    op.execute("DELETE FROM scoring_params WHERE sport = 'wavekite'")
    op.execute("""
        UPDATE spot_submissions
        SET payload = jsonb_set(
            payload,
            '{sports}',
            COALESCE((SELECT jsonb_agg(value) FROM jsonb_array_elements(payload->'sports') value
                      WHERE value <> '"wavekite"'::jsonb), '[]'::jsonb)
        )
        WHERE jsonb_typeof(payload->'sports') = 'array' AND (payload->'sports') ? 'wavekite'
    """)


def downgrade():
    # The old representation can be reconstructed for derived Wavekite spots.
    op.execute("""
        UPDATE spots
        SET sports = array_append(sports, 'wavekite')
        WHERE style @> ARRAY['wavekite']::varchar[]
          AND NOT sports @> ARRAY['wavekite']::varchar[]
    """)
