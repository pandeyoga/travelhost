import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// RouteMapInteractive.jsx — peta rute (Leaflet + CARTO light). Polyline penuh (redup) +
// polyline ter-highlight sampai titik aktif (driven oleh scroll/ScrollStory). Imperatif, ringan.
function dotIcon(color, active) {
  const s = active ? 18 : 12;
  return L.divIcon({
    className: "rm-dot",
    html: `<div style="width:${s}px;height:${s}px;border-radius:50%;background:${color};border:3px solid #fff;box-shadow:0 0 0 3px ${color}44;"></div>`,
    iconSize: [s, s],
    iconAnchor: [s / 2, s / 2],
  });
}

export default function RouteMapInteractive({ points = [], activeIndex = 0, testId = "route-map" }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const groupRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;
    const valid = points.filter((p) => p.lat != null && p.lng != null).map((p) => [p.lat, p.lng]);
    const map = L.map(containerRef.current, { zoomControl: false, scrollWheelZoom: false, dragging: true }).setView(valid[0] || [-7.5, 110], 7);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 19, attribution: '&copy; OpenStreetMap &copy; CARTO',
    }).addTo(map);
    groupRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    const t = setTimeout(() => {
      map.invalidateSize();
      if (valid.length > 1) { try { map.fitBounds(valid, { padding: [40, 40] }); } catch (e) { /* noop */ } }
    }, 220);
    return () => { clearTimeout(t); map.remove(); mapRef.current = null; groupRef.current = null; };
  }, [points]);

  useEffect(() => {
    const map = mapRef.current;
    const group = groupRef.current;
    if (!map || !group) return;
    group.clearLayers();
    const valid = points.filter((p) => p.lat != null && p.lng != null).map((p) => [p.lat, p.lng]);
    if (valid.length > 1) {
      L.polyline(valid, { color: "#94a3b8", weight: 3, opacity: 0.45, dashArray: "6 8" }).addTo(group);
      const upto = valid.slice(0, Math.max(2, activeIndex + 1));
      if (upto.length > 1) L.polyline(upto, { color: "#0ea5b7", weight: 5, opacity: 0.95 }).addTo(group);
    }
    points.forEach((p, i) => {
      if (p.lat == null || p.lng == null) return;
      const active = i === activeIndex;
      L.marker([p.lat, p.lng], { icon: dotIcon(active ? "#0c1430" : "#0ea5b7", active) })
        .addTo(group)
        .bindTooltip(p.name, { permanent: active, direction: "top", offset: [0, -6] });
    });
    const a = points[activeIndex];
    if (a && a.lat != null) { try { map.panTo([a.lat, a.lng], { animate: true, duration: 0.6 }); } catch (e) { /* noop */ } }
  }, [points, activeIndex]);

  return <div ref={containerRef} data-testid={testId} style={{ height: "100%", width: "100%", minHeight: 340, borderRadius: 16, overflow: "hidden", zIndex: 0 }} />;
}
