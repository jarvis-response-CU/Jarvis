"""Hurricane data the map reads from the database (the team's Miami tables)."""

import json

from sqlalchemy import text

from jarvis.inbox import engine

# Each map layer's query; every column but geometry becomes a feature property.
LAYERS = {
    "tracks": "select sid, name, season, max_wind_kt, geometry from miami.storm_tracks order by season",
    # Widest (34 kt) first so the stronger bands draw on top.
    "windswaths": "select storm_id, wind_kt, geometry from miami.storm_windswaths order by wind_kt",
    "surge_zones": "select surge_zone, geometry from miami.surge_zones where surge_zone is not null",
    "fire_stations": "select name, address, city, geometry from miami.fire_stations",
    # FEMA rounds claim locations to 0.1 degrees, so claims are only placed by
    # their census tract. Claims on tracts NRI doesn't have (older boundaries) drop out.
    "tracts": """
        select shape.tractfips, risk.population, risk.hrcn_riskr, risk.hrcn_ealt,
               coalesce(claims.claim_count, 0) as claim_count,
               coalesce(claims.paid, 0) as paid,
               shape.geometry
        from miami.tract_shapes shape
        join miami.nri_tracts risk using (tractfips)
        left join (
            select censustract::bigint::text as tractfips,
                   count(*) as claim_count,
                   sum(paid_total::float) as paid
            from miami.nfip_claims
            where censustract is not null
            group by 1
        ) claims using (tractfips)
    """,
}


def features(layer):
    """One of LAYERS as a GeoJSON FeatureCollection."""
    if layer not in LAYERS:
        raise KeyError(f"no hurricane layer called {layer!r}")
    with engine().connect() as connection:
        rows = connection.execute(text(LAYERS[layer])).mappings().all()

    collection = []
    for row in rows:
        properties = dict(row)
        geometry = json.loads(properties.pop("geometry"))
        collection.append({"type": "Feature", "geometry": geometry, "properties": properties})
    return {"type": "FeatureCollection", "features": collection}
