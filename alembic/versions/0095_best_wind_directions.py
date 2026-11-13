"""Add researched best wind directions to spots.

Revision ID: 0095_best_wind_directions
Revises: 0094_campaign_run_evidence
"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0095_best_wind_directions"
down_revision = "0094_campaign_run_evidence"
branch_labels = None
depends_on = None


# Immutable snapshot for this migration. Do not import the mutable application
# seed here: a historical revision must produce the same rows after seed data
# evolves. The compact tuple keeps the evidence readable without duplicating
# the seed helper's implementation.
RESEARCH_ROWS = (
    ("tarifa-los-lances", ("E", "W"), "https://www.windmaster.app/blog/kitesurfing-tarifa", "Kitesurfing in Tarifa: spots and winds", "Windmaster", "unreviewed"),
    ("tarifa-valdevaqueros", ("E", "ENE", "W"), "https://www.windmaster.app/blog/kitesurfing-tarifa", "Kitesurfing in Tarifa: spots and winds", "Windmaster", "unreviewed"),
    ("tarifa-balneario", ("E", "ENE"), "https://www.windmaster.app/blog/kitesurfing-tarifa", "Kitesurfing in Tarifa: spots and winds", "Windmaster", "unreviewed"),
    ("tarifa-punta-paloma", ("E", "ENE"), "https://www.windmaster.app/blog/kitesurfing-tarifa", "Kitesurfing in Tarifa: spots and winds", "Windmaster", "unreviewed"),
    ("tarifa-arte-vida", ("E", "ENE"), "https://www.windmaster.app/blog/kitesurfing-tarifa", "Kitesurfing in Tarifa: spots and winds", "Windmaster", "unreviewed"),
    ("sardinia-porto-pollo", ("W", "NW"), "https://www.ventosurf.com/spot/porto-pollo-sardinien", "Porto Pollo Sardinia", "VentoSurf", "verified"),
    ("sardinia-capo-mannu", ("NE", "E", "SE"), "https://surfomondo.it/spot/capo-mannu", "Capo Mannu: spot e condizioni surf", "Surfomondo", "verified"),
    ("sardinia-poetto", ("S", "SE"), "https://aurabeach.app/blog/spiagge-kite-windsurf-sardegna", "Migliori spiagge per kite e windsurf in Sardegna", "AURA Beach", "unreviewed"),
    ("laboe", ("NE", "SW"), "https://kiel.surfers-p.de/spot-laboe", "Spot Laboe", "Wassersport Center Laboe", "verified"),
    ("stein", ("N", "NE", "NW"), "https://www.spotnetz.de/w/deutschland/schleswig-holstein/kieler-bucht/", "Kieler Bucht Spotguide", "Spotnetz", "unreviewed"),
    ("schilksee", ("NE", "E", "SW"), "https://www.spotnetz.de/w/deutschland/schleswig-holstein/kieler-bucht/", "Kieler Bucht Spotguide", "Spotnetz", "unreviewed"),
    ("heidkate", ("W", "NW", "N", "NE"), "https://www.kite-buddy.de/kitespot-heidkate", "Kitespot Heidkate", "KITE BUDDY", "unreviewed"),
    ("fehmarn-wulfener-hals", ("W", "NW", "E", "SE"), "https://surfspot.de/surfspots/europa/deutschland/wulfener-hals-fehmarn/", "Wulfener Hals (Fehmarn)", "surfspot.de", "verified"),
    ("fuerteventura-sotavento", ("N", "NE"), "https://windmaster.app/blog/kitesurfing-in-fuerteventura", "Kitesurfing in Fuerteventura", "Windmaster", "verified"),
    ("fuerteventura-flag-beach", ("NW", "N", "NE"), "https://kitewithjaja.com/en/guides/kitesurfing-canary-islands/", "Kitesurfing Canary Islands", "Kite with Jaja", "verified"),
    ("fuerteventura-el-cotillo", ("N", "NW"), "https://windmaster.app/blog/kitesurfing-in-fuerteventura", "Kitesurfing in Fuerteventura", "Windmaster", "verified"),
    ("fuerteventura-majanicho", ("E",), "https://kitewithjaja.com/en/guides/kitesurfing-canary-islands/", "Kitesurfing Canary Islands", "Kite with Jaja", "verified"),
    ("fuerteventura-matas-bay", ("N", "NE"), "https://windmaster.app/blog/kitesurfing-in-fuerteventura", "Kitesurfing in Fuerteventura", "Windmaster", "verified"),
    ("lanzarote-costa-teguise", ("N", "NE"), "https://www.casalosalisios.com/blog/windsurfing-costa-teguise/", "Windsurfing in Costa Teguise", "Casa Los Alisios", "verified"),
    ("tenerife-el-medano", ("NE", "ENE"), "https://www.hightech.be/site/assets/files/2621/el_medano_duotone_pro_dpc.pdf", "El Médano Duotone Pro Center spot description", "Duotone Pro Center", "verified"),
    ("gran-canaria-pozo-izquierdo", ("N", "NE"), "https://www.pozowinds.com/spots-windsurf-gran-canaria/", "Windsurf spots Gran Canaria", "Pozowinds", "unreviewed"),
    ("rhodes-prasonisi", ("NW",), "https://hanglos.nl/kitereizen/rhodos", "Kitesurfen op Rhodos", "Hanglos", "unreviewed"),
    ("rhodes-theologos", ("W", "NW"), "https://hanglos.nl/kitereizen/rhodos", "Kitesurfen op Rhodos", "Hanglos", "unreviewed"),
    ("naxos-mikri-vigla", ("N", "NE"), "https://www.greeka.com/cyclades/naxos/sports/windsurfing/", "Windsurfing in Naxos", "Greeka", "unreviewed"),
    ("paros-pounda", ("N", "NE"), "https://www.greeka.com/cyclades/paros/sports/windsurfing/", "Windsurfing in Paros", "Greeka", "unreviewed"),
    ("kos-psalidi", ("W", "NW"), "https://www.greeka.com/dodecanese/kos/sports/windsurfing/", "Windsurfing in Kos", "Greeka", "unreviewed"),
    ("lemnos-keros", ("N", "NE"), "https://www.surfclubkeros.com/", "Keros Surf Club spot information", "Surf Club Keros", "unreviewed"),
    ("sicily-lo-stagnone", ("N",), "https://www.dpc-sicily.com/fileadmin/user_upload/dpcsicily/travel_information/DPC_Sicily_Travel_Information.pdf", "DPC Sicily travel information", "Duotone Pro Center Sicily", "verified"),
    ("languedoc-leucate", ("NW", "SE"), "https://spots.mywatersessions.com/spots/leucate-la-franqui", "Leucate / La Franqui spot guide", "MyWaterSessions", "verified"),
    ("zeeland-brouwersdam", ("SW", "W", "NW"), "https://www.hangloose.nl/brouwersdam/", "Brouwersdam spot information", "Hangloose", "unreviewed"),
    ("ericeira-ribeira-dilhas", ("NE", "E", "SE"), "https://makaisurf.app/spots/ribeira-dilhas", "Ribeira d'Ilhas surf guide", "Makai", "verified"),
    ("ericeira-coxos", ("E", "SE"), "https://www.cm-mafra.pt/cmmafra/uploads/writer_file/document/2999/guiasurf2020_digital_leve_v.pdf", "Ericeira surf guide", "Município de Mafra", "unreviewed"),
    ("ericeira-sao-lourenco", ("E", "SE"), "https://www.cm-mafra.pt/cmmafra/uploads/writer_file/document/2999/guiasurf2020_digital_leve_v.pdf", "Ericeira surf guide", "Município de Mafra", "unreviewed"),
    ("ericeira-foz-do-lizandro", ("E", "SE"), "https://www.cm-mafra.pt/cmmafra/uploads/writer_file/document/2999/guiasurf2020_digital_leve_v.pdf", "Ericeira surf guide", "Município de Mafra", "verified"),
    ("peniche-supertubos", ("N", "NE", "E"), "https://www.visitportugal.com/en/content/surfing-and-bodyboarding", "Surfing and bodyboarding", "Turismo de Portugal", "unreviewed"),
    ("peniche-baleal", ("S", "SW"), "https://www.cm-peniche.pt/visitar/surf", "Surf in Peniche", "Município de Peniche", "unreviewed"),
    ("nazare-praia-do-norte", ("E", "SE"), "https://www.visitportugal.com/en/content/nazare-waves", "Nazaré waves", "Turismo de Portugal", "unreviewed"),
    ("cascais-carcavelos", ("N", "NE", "NW"), "https://www.cascais.pt/sites/default/files/anexos/gerais/impacte_da_urbanizacao_de_carcavelos-sul_sobre_o_regime_de_ventos_na_praia.pdf", "Wind regime at Carcavelos beach", "Município de Cascais", "unreviewed"),
    ("cascais-guincho", ("E", "SE"), "https://www.visitcascais.com/en/locais/guincho-beach", "Guincho Beach", "Visit Cascais", "unreviewed"),
    ("sintra-praia-grande", ("E", "SE"), "https://visitsintra.travel/en/visit/beaches/praia-grande", "Praia Grande", "Visit Sintra", "unreviewed"),
    ("basque-mundaka", ("S", "SW"), "https://kirolur.bizkaia.eus/documents/d/kirolur/a-2025-03-05-bizkaia-region-europea_en", "Bizkaia European Region of Sport", "Bizkaia", "verified"),
    ("basque-zarautz", ("S", "SE"), "https://turismo.euskadi.eus/en/surf-spots/zarautz/webtur00-content/en/", "Zarautz surf spot", "Basque Country Tourism", "unreviewed"),
    ("cantabria-somo", ("S", "SE", "E", "NE"), "https://turismodecantabria.com/wp-content/uploads/2023/06/aeaa3219-aa7b-ab9b-8651-3d1384980b0c.pdf", "Cantabria surf guide", "Cantabria Tourism", "verified"),
    ("asturias-rodiles", ("S", "SW"), "https://www.turismoasturias.es/en/descubre/costa/playas/playa-de-rodiles", "Rodiles beach", "Turismo Asturias", "unreviewed"),
    ("landes-la-graviere", ("E", "NE"), "https://conditionssurf.fr/spots/hossegor", "Surf report Hossegor", "Conditions Surf", "verified"),
    ("landes-la-sud", ("E", "NE"), "https://hossegorfrance.com/breaks/", "Hossegor breaks", "Hossegor France", "unreviewed"),
    ("landes-les-estagnots", ("E", "NE"), "https://conditionssurf.fr/spots/hossegor", "Surf report Hossegor", "Conditions Surf", "verified"),
    ("donegal-bundoran-peak", ("ESE", "SE", "SSE"), "https://shoreforecast.com/en/ireland/bundoran-the-peak/", "Bundoran – The Peak surf forecast", "Shore Forecast", "verified"),
    ("clare-lahinch", ("E", "SE"), "https://www.discoverireland.ie/clare/lahinch-beach", "Lahinch Beach", "Discover Ireland", "unreviewed"),
    ("caithness-thurso-east", ("S", "SW"), "https://www.surf-forecast.com/breaks/Thurso-East", "Thurso East surf forecast", "Surf-Forecast", "unreviewed"),
    ("cornwall-fistral", ("E", "SE"), "https://www.visitnewquay.org/things-to-do/beaches/fistral-beach", "Fistral Beach", "Visit Newquay", "unreviewed"),
)

VERIFIED_NOTE = "Quelle nennt diese Richtungen als beste bzw. nutzbare Windrichtungen."
UNREVIEWED_NOTE = (
    "Aus dem regionalen Spotguide und der Küstenausrichtung abgeleitet; "
    "redaktionelle Einzelprüfung ausstehend."
)


def upgrade() -> None:
    op.add_column(
        "spots",
        sa.Column(
            "best_wind_directions",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
    )
    connection = op.get_bind()
    checked_at = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
    for slug, directions, url, title, publisher, verification_status in RESEARCH_ROWS:
        row = connection.execute(
            sa.text("""
                UPDATE spots
                SET best_wind_directions = CAST(:directions AS varchar[]),
                    updated_at = now()
                WHERE slug = :slug
                RETURNING id
            """),
            {"slug": slug, "directions": list(directions)},
        ).first()
        if row is None:
            continue
        connection.execute(
            sa.text("""
                INSERT INTO spot_content_sources (
                    id, spot_id, field_path, url, title, publisher, checked_at,
                    verification_status, note, created_by, reviewed_by,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :spot_id, 'best_wind_directions', :url,
                    :title, :publisher, :checked_at, :verification_status, :note,
                    'migration:0095', :reviewed_by, now(), now()
                )
                ON CONFLICT (spot_id, field_path, url) DO UPDATE SET
                    title = EXCLUDED.title,
                    publisher = EXCLUDED.publisher,
                    checked_at = EXCLUDED.checked_at,
                    verification_status = EXCLUDED.verification_status,
                    note = EXCLUDED.note,
                    reviewed_by = EXCLUDED.reviewed_by,
                    updated_at = now()
            """),
            {
                "spot_id": row.id,
                "url": url,
                "title": title,
                "publisher": publisher,
                "checked_at": checked_at,
                "verification_status": verification_status,
                "note": VERIFIED_NOTE if verification_status == "verified" else UNREVIEWED_NOTE,
                "reviewed_by": (
                    "migration:0095"
                    if verification_status == "verified"
                    else None
                ),
            },
        )


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM spot_content_sources
        WHERE field_path = 'best_wind_directions'
          AND created_by = 'migration:0095'
    """))
    op.drop_column("spots", "best_wind_directions")

