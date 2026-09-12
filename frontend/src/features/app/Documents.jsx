import { useState } from "react";
import { Navigate } from "react-router-dom";
import { FileCog, Hash, Landmark } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { canAccess } from "@/config/navigationConfig";
import DocLayoutPanel from "@/components/documents/DocLayoutPanel";
import NumberingPanel from "@/components/documents/NumberingPanel";
import InvoiceConfigPanel from "@/components/documents/InvoiceConfigPanel";

const TABS = [
  ["layout", "Template & Tampilan", FileCog],
  ["numbering", "Penomoran", Hash],
  ["payment", "DP, Jatuh Tempo & Rekening", Landmark],
];

export default function Documents() {
  const { user } = useAuth();
  const [tab, setTab] = useState("layout");
  if (user && !canAccess(user.role, "documents")) return <Navigate to="/app/dashboard" replace />;
  return (
    <div className="space-y-4" data-testid="documents-page">
      <div className="tab-bar">
        {TABS.map(([k, l, Icon]) => (
          <button key={k} className={`tab-button ${tab === k ? "active" : ""}`} onClick={() => setTab(k)} data-testid={`tab-documents-${k}`}>
            <Icon size={14} /> {l}
          </button>
        ))}
      </div>
      {tab === "layout" && <DocLayoutPanel />}
      {tab === "numbering" && <NumberingPanel />}
      {tab === "payment" && <InvoiceConfigPanel />}
    </div>
  );
}
