import { useEffect, useState } from "react";
import { Gauge, Play, CheckCircle2 } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatQty } from "@/utils/formatters";

// E9: input odometer saat Mulai (start) / Selesai (end). Boleh dilewati (opsional).
export default function OdometerDialog({ open, mode, task, onOpenChange, onConfirm }) {
  const isStart = mode === "start";
  const [value, setValue] = useState("");

  useEffect(() => {
    if (open) setValue(task?.vehicle_odometer != null ? String(task.vehicle_odometer) : "");
  }, [open, task, mode]);

  const start = task?.odometer_start;
  const preview = (!isStart && start != null && value !== "" && Number(value) >= Number(start))
    ? Number(value) - Number(start) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm" data-testid="odometer-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isStart ? <Play size={16} className="text-[#007AFF]" /> : <CheckCircle2 size={16} className="text-[#34C759]" />}
            {isStart ? "Mulai Perjalanan" : "Selesaikan Trip"}
          </DialogTitle>
          <DialogDescription>
            {isStart ? "Catat odometer awal (opsional, untuk hitung jarak akurat)." : "Catat odometer akhir untuk menghitung jarak tempuh."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {task?.vehicle_name ? <div className="text-[12.5px] text-[#6B6B73]">Armada: <b className="text-[#1C1C1E]">{task.vehicle_name}</b>{task.vehicle_plate ? ` · ${task.vehicle_plate}` : ""}</div> : null}
          {!isStart && start != null ? <div className="text-[12.5px] text-[#6B6B73]">Odometer awal: <b className="tabular-nums">{formatQty(start)} km</b></div> : null}
          <div>
            <Label className="flex items-center gap-1.5 text-[12px]"><Gauge size={13} /> Odometer {isStart ? "Awal" : "Akhir"} (km)</Label>
            <Input type="number" value={value} onChange={(e) => setValue(e.target.value)} placeholder="mis. 84500" data-testid="odo-input" />
          </div>
          {preview != null ? (
            <div className="rounded-[10px] bg-[#F0F9F2] px-3 py-2 text-[12.5px] text-[#1B7A3D]" data-testid="odo-preview">
              Jarak tempuh: <b className="tabular-nums">{formatQty(preview)} km</b>
            </div>
          ) : null}
        </div>
        <DialogFooter className="gap-2">
          <button className="secondary-button" onClick={() => onConfirm(null)} data-testid="odo-skip">Lewati</button>
          <button className="primary-button" disabled={value === ""} onClick={() => onConfirm(Number(value))} data-testid="odo-confirm">
            {isStart ? "Mulai" : "Selesai"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
