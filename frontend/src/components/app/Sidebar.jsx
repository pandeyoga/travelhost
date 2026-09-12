import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronDown, ChevronRight, Clock, Layers3, LogOut } from "lucide-react";
import { navForRole } from "@/config/navigationConfig";
import { useAuth } from "@/context/AuthContext";
import { initials } from "@/utils/formatters";

const ROLE_LABEL = { owner: "Pemilik", ops_admin: "Admin Operasional", marketing_admin: "Admin Marketing", driver: "Driver" };

export default function Sidebar({ open, onClose, onNavigate }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const tree = navForRole(user?.role);

  const activeGroupId = (() => {
    for (const entry of tree) {
      if (entry.type === "group" && entry.items.some((i) => i.path === location.pathname)) return entry.groupId;
    }
    return null;
  })();

  const [expanded, setExpanded] = useState(() => new Set(activeGroupId ? [activeGroupId] : ["operasional", "master"]));

  useEffect(() => {
    if (activeGroupId) {
      setExpanded((prev) => {
        if (prev.has(activeGroupId)) return prev;
        const next = new Set(prev);
        next.add(activeGroupId);
        return next;
      });
    }
  }, [activeGroupId]);

  const toggleGroup = (groupId) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  };

  return (
    <>
      <div
        data-testid="sidebar-backdrop"
        className={`sidebar-backdrop ${open ? "open" : ""}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside data-testid="app-sidebar" className={`app-sidebar ${open ? "open" : ""}`}>
        <div className="sidebar-brand">
          <div data-testid="brand-mark" className="sidebar-brand-mark"><Layers3 size={17} /></div>
          <div className="sidebar-brand-text">
            <span data-testid="app-brand" className="t1">RahazaTrans</span>
            <span className="t2">Fleet · Booking · CRM</span>
          </div>
        </div>

        <nav data-testid="main-navigation" className="sidebar-nav" aria-label="Main">
          {tree.map((entry) => {
            if (entry.type === "standalone") {
              const Icon = entry.icon;
              const isActive = location.pathname === entry.path;
              return (
                <Link
                  key={entry.id}
                  to={entry.path}
                  onClick={onNavigate}
                  data-testid={`nav-${entry.id}`}
                  className={`sidebar-item ${isActive ? "active" : ""}`}
                  aria-current={isActive ? "page" : undefined}
                >
                  <Icon size={17} />
                  <span className="label">{entry.label}</span>
                </Link>
              );
            }
            const GroupIcon = entry.icon;
            const isOpen = expanded.has(entry.groupId);
            const groupHasActive = entry.items.some((i) => i.path === location.pathname);
            return (
              <div key={entry.groupId} className="sidebar-group" data-testid={`nav-group-${entry.groupId}`}>
                <button
                  className={`sidebar-group-header ${groupHasActive ? "has-active" : ""}`}
                  onClick={() => toggleGroup(entry.groupId)}
                  aria-expanded={isOpen}
                  data-testid={`nav-group-toggle-${entry.groupId}`}
                >
                  <GroupIcon size={14} className="group-icon" />
                  <span className="group-label">{entry.label}</span>
                  {isOpen ? <ChevronDown size={12} className="chevron" /> : <ChevronRight size={12} className="chevron" />}
                </button>
                {isOpen && (
                  <div className="sidebar-group-items">
                    {entry.items.map((item) => {
                      const ItemIcon = item.icon;
                      const isActive = item.path === location.pathname;
                      return (
                        <Link
                          key={item.id}
                          to={item.path}
                          onClick={onNavigate}
                          data-testid={`nav-${item.id}`}
                          className={`sidebar-item sidebar-sub-item ${isActive ? "active" : ""}`}
                          aria-current={isActive ? "page" : undefined}
                        >
                          <ItemIcon size={14} />
                          <span className="label">{item.label}</span>
                          {item.comingSoon && (
                            <span className="cs-badge-inline" title="Segera hadir"><Clock size={9} /></span>
                          )}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip" data-testid="user-menu-button">
            <div className="avatar">{initials(user?.name)}</div>
            <div className="user-text">
              <span className="name">{user?.name}</span>
              <span className="role">{ROLE_LABEL[user?.role] || user?.role}</span>
            </div>
          </div>
          <button data-testid="logout-button" className="secondary-button" onClick={logout}>
            <LogOut size={14} /> Logout
          </button>
        </div>
      </aside>
    </>
  );
}
