import { ExternalLink, MapPinned } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import LiveMap from "@/components/app/LiveMap";

export default function DriverNavDialog({ open, task, onOpenChange }) {
  const lat = task?.dest_lat;
  const lng = task?.dest_lng;
  const hasCoords = lat != null && lng != null;
  const name = task?.destination || task?.dest_display || "Tujuan";
  const gmaps = hasCoords ? `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}` : null;
  const osm = hasCoords ? `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=14/${lat}/${lng}` : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl" data-testid="dw-nav-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><MapPinned size={16} className="text-[#FF3B30]" /> Navigasi ke {name}</DialogTitle>
          <DialogDescription>Peta tujuan (OpenStreetMap). Buka aplikasi peta untuk navigasi belok-per-belok.</DialogDescription>
        </DialogHeader>
        {hasCoords ? (
          <>
            <div style={{ height: 380 }} className="overflow-hidden rounded-[14px]">
              <LiveMap destination={{ lat, lng, name }} testId="dw-nav-map" />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <a className="primary-button !h-9" href={gmaps} target="_blank" rel="noreferrer" data-testid="dw-nav-gmaps">
                <ExternalLink size={14} /> Buka di Google Maps
              </a>
              <a className="secondary-button !h-9" href={osm} target="_blank" rel="noreferrer" data-testid="dw-nav-osm">
                <ExternalLink size={14} /> Buka di OpenStreetMap
              </a>
            </div>
          </>
        ) : (
          <div className="rounded-[12px] border border-dashed border-[#E2E3E6] bg-[#FAFAFB] p-6 text-center text-[13px] text-[#8E8E93]" data-testid="dw-nav-nocoords">
            Koordinat tujuan belum tersedia. Tim dispatch akan melengkapi titik tujuan saat assign.
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
