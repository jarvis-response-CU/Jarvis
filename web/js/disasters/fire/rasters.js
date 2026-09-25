/*
 * References:
 *   https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation
 *   https://developers.arcgis.com/rest/services-reference/enterprise/export-image/
 *   https://leafletjs.com/examples/extending/extending-2-layers.html
 */

const USFS_IMAGERY = "https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation";
const USFS_ATTRIBUTION = "&copy; USDA Forest Service";

const WEB_MERCATOR_EXTENT = 20037508.342789244;

// These services have no tile cache, so each tile asks exportImage for its own bbox.
const ImageServerTiles = L.TileLayer.extend({
  getTileUrl(coords) {
    const pixels = this.getTileSize().x;
    const worldWidth = 2 * WEB_MERCATOR_EXTENT;
    const worldPixels = 256 * 2 ** coords.z;
    const tileSpan = (worldWidth * pixels) / worldPixels;

    const xmin = -WEB_MERCATOR_EXTENT + coords.x * tileSpan;
    const xmax = xmin + tileSpan;
    const ymax = WEB_MERCATOR_EXTENT - coords.y * tileSpan;
    const ymin = ymax - tileSpan;

    const params = new URLSearchParams({
      bbox: `${xmin},${ymin},${xmax},${ymax}`,
      bboxSR: "3857",
      imageSR: "3857",
      size: `${pixels},${pixels}`,
      f: "image",
      ...this.options.exportParams,
    });
    return `${this.options.serviceUrl}/exportImage?${params}`;
  },
});

function usfsLayer(service, options) {
  return new ImageServerTiles("", {
    pane: "rasters",
    // Requests take ~1 s at any size, so 512 px tiles mean a quarter as many queued requests.
    tileSize: 512,
    serviceUrl: `${USFS_IMAGERY}/${service}/ImageServer`,
    attribution: USFS_ATTRIBUTION,
    ...options,
  });
}

// Density rasters use 0 for "nothing here"; this makes those cells transparent instead of black.
const TRANSPARENT_EMPTY = { format: "png32", noData: "0" };

export const hazard = {
  name: "hazard",
  layer: usfsLayer("USFS_EDW_RMRS_WildfireHazardPotentialClassified", {
    opacity: 0.55,
    exportParams: { format: "png" },
  }),
  reloadOnMove: false,
};

export const buildings = {
  name: "buildings",
  layer: usfsLayer("USFS_EDW_RMRS_WRC_BuildingDensity", {
    opacity: 0.7,
    exportParams: TRANSPARENT_EMPTY,
  }),
  reloadOnMove: false,
};

export const population = {
  name: "population",
  layer: usfsLayer("USFS_EDW_RMRS_WRC_PopulationDensity", {
    opacity: 0.7,
    exportParams: TRANSPARENT_EMPTY,
  }),
  reloadOnMove: false,
};
