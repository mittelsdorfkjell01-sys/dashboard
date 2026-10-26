from app.seed.safety_notices import INITIAL_SAFETY_NOTICES, initial_safety_notice


def test_initial_safety_notices_cover_the_supplied_catalogue_without_duplicate_aliases():
    aliases = [name for names, _notice in INITIAL_SAFETY_NOTICES for name in names]

    assert len(INITIAL_SAFETY_NOTICES) == 46
    assert len(aliases) == len(set(aliases))
    assert initial_safety_notice("Ribeira d'Ilhas") == initial_safety_notice("Ribeira d’Ilhas")
    assert initial_safety_notice("Valdevaqueros") == initial_safety_notice(
        "Valdevaqueros – Tarifa"
    )
    assert initial_safety_notice("Nicht in der Liste") is None
