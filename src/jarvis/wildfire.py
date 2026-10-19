# References:
#   https://developers.arcgis.com/rest/services-reference/enterprise/query-map-service-layer/
#   https://bouldercounty.gov/property-and-land/assessor/data-download/

"""Download the Boulder wildfire source data into data/raw/wildfire/.

Map layers are saved as GeoJSON, one file per layer. The assessor tables are
saved as the CSVs the county publishes. Nothing is joined or cleaned here.

Run it with:  python -m jarvis.wildfire
"""

import json
import urllib.parse
import urllib.request

from jarvis.config import load_settings

LAYERS = {
    "parcels": "https://maps.bouldercounty.org/arcgis/rest/services/Emap/BOCO_Parcels/MapServer/0",
    "building_footprints": "https://gis.bouldercolorado.gov/ags_svr3/rest/services/pw/BuildingFootprints/MapServer/0",
    "fire_perimeters": "https://maps.bouldercounty.org/arcgis/rest/services/HAZARD/FIRE_WILDFIRE_HISTORY/MapServer/0",
    "marshall_fire_parcels": "https://services3.arcgis.com/APrbG4iiuZuctqvI/ArcGIS/rest/services/Boulder_County_Parcels_2021_Marshall_Fire_v3/FeatureServer/6",
    "fire_stations": "https://gis.bouldercolorado.gov/ags_svr1/rest/services/fire/FireStations/MapServer/0",
    "response_times": "https://gis.bouldercolorado.gov/ags_svr1/rest/services/fire/ResponseTimesOpenData/MapServer/0",
}
ASSESSOR_URL = "https://assessor.boco.solutions/ASR_PublicDataFiles"
ASSESSOR_TABLES = ["Account_Parcels", "Values", "Buildings", "Land", "Sales", "Permits"]
# The City of Boulder's server answers 403 to Python's default user agent.
HEADERS = {"User-Agent": "jarvis-wildfire-fetch"}


def open_url(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120)


def get_json(url, params):
    with open_url(f"{url}?{urllib.parse.urlencode(params)}") as response:
        data = json.load(response)
    if "error" in data:
        raise RuntimeError(f"{url} returned an error: {data['error']}")
    return data


def count_features(url):
    return get_json(f"{url}/query", {"where": "1=1", "returnCountOnly": "true", "f": "json"})["count"]


def fetch_layer(url):
    """Every feature in an ArcGIS layer as one GeoJSON FeatureCollection, in lat/long."""
    info = get_json(url, {"f": "json"})
    id_field = next(field["name"] for field in info["fields"] if field["type"] == "esriFieldTypeOID")
    expected = count_features(url)

    features = []
    while len(features) < expected:
        page = get_json(f"{url}/query", {
            "where": "1=1",
            "outFields": "*",
            "outSR": 4326,
            # Without a fixed sort order, pages can overlap or skip rows.
            "orderByFields": id_field,
            "resultOffset": len(features),
            "resultRecordCount": info["maxRecordCount"],
            "f": "geojson",
        })["features"]
        if not page:
            break
        features.extend(page)

    unique_ids = {feature["id"] for feature in features}
    if len(unique_ids) != len(features):
        raise RuntimeError(f"{url} returned the same feature on more than one page")

    # Live layers like response times can gain rows during a long download,
    # so the final check uses a fresh count.
    final_count = count_features(url)
    if len(features) != final_count:
        raise RuntimeError(f"{url} has {final_count} features but {len(features)} were downloaded")
    return {"type": "FeatureCollection", "features": features}


def main():
    folder = load_settings().raw_dir / "wildfire"
    folder.mkdir(parents=True, exist_ok=True)

    for name, url in LAYERS.items():
        collection = fetch_layer(url)
        (folder / f"{name}.geojson").write_text(json.dumps(collection))
        print(f"saved {len(collection['features'])} features to {name}.geojson")

    for table in ASSESSOR_TABLES:
        path = folder / f"{table.lower()}.csv"
        with open_url(f"{ASSESSOR_URL}/{table}.csv") as response:
            path.write_bytes(response.read())
        print(f"saved {path.name}")


if __name__ == "__main__":
    main()
