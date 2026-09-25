import { fetchJson } from "../../util.js";

const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
const MPH_TO_MPS = 0.44704;

// NWS gives wind as text like "6 mph" or "5 to 10 mph" from "NE"; the higher
// speed is used because the faster wind drives the spread.
function parseWind(speedText, directionText) {
  let fastestMph = 0;
  const numbers = speedText.match(/\d+(\.\d+)?/g);
  if (numbers) {
    for (const number of numbers) {
      fastestMph = Math.max(fastestMph, Number(number));
    }
  }

  const index = COMPASS.indexOf(directionText);
  return {
    speedMps: fastestMph * MPH_TO_MPS,
    fromDeg: index >= 0 ? index * 22.5 : 0,
    label: `${speedText} from ${directionText || "—"}`,
  };
}

export async function weatherAt(lat, lng) {
  const point = await fetchJson(`https://api.weather.gov/points/${lat.toFixed(4)},${lng.toFixed(4)}`);
  const hourly = await fetchJson(point.properties.forecastHourly);
  const now = hourly.properties.periods[0];

  let humidity = null;
  const humidityPercent = now.relativeHumidity?.value;
  if (humidityPercent != null) {
    humidity = `${humidityPercent}%`;
  }

  return {
    conditions: `${now.temperature}°${now.temperatureUnit}, ${now.shortForecast}`,
    humidity,
    wind: parseWind(now.windSpeed, now.windDirection),
  };
}
