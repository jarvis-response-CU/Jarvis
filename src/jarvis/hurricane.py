"""Hurricane data the map reads from the database (the team's Miami tables)."""

import json

from sqlalchemy import text

from jarvis.inbox import engine


def storm_tracks():
    """Every historical storm track near Miami, as a GeoJSON FeatureCollection."""
    query = text("select sid, name, season, max_wind_kt, geometry from miami.storm_tracks order by season")
    with engine().connect() as connection:
        rows = connection.execute(query).mappings().all()

    features = []
    for row in rows:
        properties = {
            "sid": row["sid"],
            "name": row["name"],
            "season": row["season"],
            "max_wind_kt": row["max_wind_kt"],
        }
        features.append({"type": "Feature", "geometry": json.loads(row["geometry"]), "properties": properties})
    return {"type": "FeatureCollection", "features": features}
