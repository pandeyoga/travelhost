import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Peta live (Leaflet + OpenStreetMap, gratis). Marker & polyline dikelola imperatif
// agar ringan (tanpa re-render React per tick). divIcon = tanpa aset gambar.
function vehicleIcon(label) {
  return L.divIcon({
    className: "lm-veh-icon",
    html:
      `<div style="display:flex;align-items:center;gap:5px;background:#007AFF;color:#fff;` +
      `padding:4px 8px;border-radius:999px;font:700 11px/1 Manrope,sans-serif;` +
      `box-shadow:0 4px 12px rgba(0,122,255,.35);white-space:nowrap;border:2px solid #fff;">` +
      `<span style="font-size:13px">\u{1F690}</span>${label || ""}</div>`,
    iconSize: [10, 10],
    iconAnchor: [10, 10],
  });
}

function dotIcon(color) {
  return L.divIcon({
    className: "lm-dot-icon",
    html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:3px solid #fff;box-shadow:0 0 0 2px ${color}55;"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

function flagIcon() {
  return L.divIcon({
    className: "lm-flag-icon",
    html:
      `<div style="display:flex;align-items:center;gap:4px;background:#FF3B30;color:#fff;` +
      `padding:3px 8px;border-radius:8px;font:700 11px/1 Manrope,sans-serif;border:2px solid #fff;` +
      `box-shadow:0 4px 12px rgba(255,59,48,.35);">\u{1F3C1} Tujuan</div>`,
    iconSize: [10, 10],
    iconAnchor: [10, 24],
  });
}

export default function LiveMap({ live = [], track = [], destination = null, testId = "live-map" }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const groupRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { zoomControl: true }).setView([-6.9147, 107.6098], 9);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    groupRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    const t = setTimeout(() => map.invalidateSize(), 250);
    return () => {
      clearTimeout(t);
      map.remove();
      mapRef.current = null;
      groupRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const group = groupRef.current;
    if (!map || !group) return;
    group.clearLayers();
    const bounds = [];

    // Polyline jejak trip terpilih.
    const linePts = [];
    for (const p of track) {
      const lat = p.lat != null ? p.lat : p[0];
      const lng = p.lng != null ? p.lng : p[1];
      if (lat != null && lng != null) {
        linePts.push([lat, lng]);
        bounds.push([lat, lng]);
      }
    }
    if (linePts.length > 1) {
      L.polyline(linePts, { color: "#007AFF", weight: 4, opacity: 0.85 }).addTo(group);
      L.marker(linePts[0], { icon: dotIcon("#34C759") }).addTo(group).bindTooltip("Mulai");
      L.marker(linePts[linePts.length - 1], { icon: dotIcon("#007AFF") }).addTo(group).bindTooltip("Posisi kini");
    }

    // Marker armada live.
    for (const v of live) {
      if (v.lat == null || v.lng == null) continue;
      const label = v.plate_number || v.vehicle_name || "";
      L.marker([v.lat, v.lng], { icon: vehicleIcon(label) })
        .addTo(group)
        .bindPopup(
          `<b>${v.vehicle_name || "-"}</b><br/>${v.plate_number || ""}<br/>Driver: ${v.driver_name || "-"}`
        );
      bounds.push([v.lat, v.lng]);
    }

    // Marker tujuan.
    if (destination && destination.lat != null && destination.lng != null) {
      L.marker([destination.lat, destination.lng], { icon: flagIcon() })
        .addTo(group)
        .bindTooltip(destination.name || "Tujuan");
      bounds.push([destination.lat, destination.lng]);
    }

    if (bounds.length === 1) {
      map.setView(bounds[0], 12);
    } else if (bounds.length > 1) {
      try {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
      } catch (e) {
        /* abaikan bounds invalid */
      }
    }
  }, [live, track, destination]);

  return (
    <div
      ref={containerRef}
      data-testid={testId}
      style={{ height: "100%", width: "100%", minHeight: 460, borderRadius: 14, overflow: "hidden", zIndex: 0 }}
    />
  );
}
