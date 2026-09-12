import { useLocation } from "react-router-dom";
import { Menu, RefreshCw } from "lucide-react";
import { PAGE_META, PAGE_TAB_TITLES } from "@/config/navigationConfig";
import NotificationBell from "@/components/app/NotificationBell";

export default function Topbar({ onToggleSidebar }) {
  const location = useLocation();
  const segment = location.pathname.split("/")[2] || "dashboard";
  const meta = PAGE_META[segment] || { title: "Beranda", kicker: "" };
  const tab = new URLSearchParams(location.search).get("tab") || "";
  const title = PAGE_TAB_TITLES[segment]?.[tab] || meta.title;

  return (
    <header className="topbar" role="banner">
      <button
        type="button"
        data-testid="sidebar-toggle-button"
        className="icon-button menu-toggle"
        onClick={onToggleSidebar}
        aria-label="Buka navigasi"
      >
        <Menu size={16} />
      </button>

      <div className="title-block">
        <nav className="breadcrumb" data-testid="breadcrumb" aria-label="Breadcrumb">
          <span className="crumb-root">Beranda</span>
          {meta.kicker ? (
            <>
              <span className="crumb-sep" aria-hidden="true">›</span>
              <span className="kicker" data-testid="page-kicker">{meta.kicker}</span>
            </>
          ) : null}
        </nav>
        <h1 data-testid="page-title" className="page-title">{title}</h1>
      </div>

      <div className="topbar-actions">
        <NotificationBell />
        <button
          className="icon-button"
          data-testid="refresh-data-button"
          onClick={() => window.location.reload()}
          aria-label="Muat ulang"
          title="Muat ulang"
        >
          <RefreshCw size={15} />
        </button>
      </div>
    </header>
  );
}
