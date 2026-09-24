const HAZARD_URL =
  "https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/USFS_EDW_RMRS_WildfireHazardPotentialClassified/ImageServer/exportImage";

// The hazard service has no tile cache, so each tile asks exportImage for its
// own Web Mercator bbox.
const WEB_MERCATOR_EXTENT = 20037508.342789244;

const HazardTiles = L.TileLayer.extend({
  getTileUrl({ x, y, z }) {
    const size = (2 * WEB_MERCATOR_EXTENT) / 2 ** z;
    const xmin = -WEB_MERCATOR_EXTENT + x * size;
    const ymax = WEB_MERCATOR_EXTENT - y * size;
    const params = new URLSearchParams({
      bbox: `${xmin},${ymax - size},${xmin + size},${ymax}`,
      bboxSR: "3857",
      imageSR: "3857",
      size: "256,256",
      format: "png",
      f: "image",
    });
    return `${HAZARD_URL}?${params}`;
  },
});

const layer = new HazardTiles("", {
  opacity: 0.55,
  attribution: "Wildfire Hazard Potential &copy; USDA Forest Service",
});

export const hazard = { name: "hazard", layer, reloadOnMove: false };
