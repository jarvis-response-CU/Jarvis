import { useMapEvents } from "react-leaflet";
import type { LatLng } from "../types";

interface MapClickHandlerProps {
  enabled: boolean;
  onPick: (point: LatLng) => void;
}

export default function MapClickHandler({ enabled, onPick }: MapClickHandlerProps) {
  useMapEvents({
    click(e) {
      if (enabled) {
        onPick({ lat: e.latlng.lat, lng: e.latlng.lng });
      }
    },
  });

  return null;
}