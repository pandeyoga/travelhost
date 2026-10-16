import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/app/ProtectedRoute";
import RoleGuard from "@/components/app/RoleGuard";
import AppShell from "@/components/app/AppShell";
import Login from "@/features/app/Login";
import Dashboard from "@/features/app/Dashboard";
import Bookings from "@/features/app/Bookings";
import DepartureCalendar from "@/features/app/DepartureCalendar";
import Dispatch from "@/features/app/Dispatch";
import DriverWorkspace from "@/features/app/DriverWorkspace";
import Vehicles from "@/features/app/Vehicles";
import Drivers from "@/features/app/Drivers";
import Customers from "@/features/app/Customers";
import MasterData from "@/features/app/MasterData";
import Crm from "@/features/app/Crm";
import Quotations from "@/features/app/Quotations";
import ContentManager from "@/features/app/ContentManager";
import Users from "@/features/app/Users";
import Finance from "@/features/app/Finance";
import Reports from "@/features/app/Reports";
import GpsTracking from "@/features/app/GpsTracking";
import Maintenance from "@/features/app/Maintenance";
import Partners from "@/features/app/Partners";
import Inbox from "@/features/app/Inbox";
import Automation from "@/features/app/Automation";
import Settings from "@/features/app/Settings";
import Documents from "@/features/app/Documents";
import AuditLog from "@/features/app/AuditLog";
import Integrations from "@/features/app/Integrations";
import TrackingHealth from "@/features/app/TrackingHealth";
import Ads from "@/features/app/Ads";
import LandingBuilder from "@/features/app/LandingBuilder";
import MediaManager from "@/features/app/MediaManager";
import LandingPage from "@/features/public/LandingPage";
import PublicLayout from "@/components/public/PublicLayout";
import PublicTrack from "@/features/public/PublicTrack";
import Home from "@/features/public/Home";
import Fleet from "@/features/public/Fleet";
import FleetDetail from "@/features/public/FleetDetail";
import Destinations from "@/features/public/Destinations";
import DestinationDetail from "@/features/public/DestinationDetail";
import Packages from "@/features/public/Packages";
import PackageDetail from "@/features/public/PackageDetail";
import Promos from "@/features/public/Promos";
import ReviewSubmit from "@/features/public/ReviewSubmit";
import TripCalculator from "@/features/public/TripCalculator";
import Quotation from "@/features/public/Quotation";
import BookingRequest from "@/features/public/BookingRequest";
import BookingWizard from "@/features/public/BookingWizard";
import BookingStatus from "@/features/public/BookingStatus";
import ThankYou from "@/features/public/ThankYou";
import Blog from "@/features/public/Blog";
import BlogDetail from "@/features/public/BlogDetail";
import About from "@/features/public/About";
import Contact from "@/features/public/Contact";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* PUBLIC SITE (surface=public) */}
          <Route element={<PublicLayout />}>
            <Route path="/lp/:slug" element={<LandingPage />} />
            <Route path="/" element={<Home />} />
            <Route path="/fleet" element={<Fleet />} />
            <Route path="/fleet/:id" element={<FleetDetail />} />
            <Route path="/destinations" element={<Destinations />} />
            <Route path="/destinations/:slug" element={<DestinationDetail />} />
            {/* A1 — halaman Paket publik (URL bahasa Inggris, sama dengan sitemap & tautan
                pratinjau CMS). `?preview=<token>` membuka paket yang belum tayang (CMS-05). */}
            <Route path="/packages" element={<Packages />} />
            <Route path="/packages/:slug" element={<PackageDetail />} />
            {/* A3 — halaman promo publik untuk trafik iklan; kode dibawa ke wizard `?promo=`. */}
            <Route path="/promo" element={<Promos />} />
            {/* CMS-07 — halaman ulasan bertoken (tautan dikirim via WhatsApp MOCK). */}
            <Route path="/review/:token" element={<ReviewSubmit />} />
            <Route path="/trip-calculator" element={<TripCalculator />} />
            <Route path="/quotation" element={<Quotation />} />
            <Route path="/booking" element={<BookingWizard />} />
            <Route path="/booking/status" element={<BookingStatus />} />
            {/* Jalur lama "minta penawaran tanpa unit" (paket wisata / lepas kunci / kebutuhan khusus) */}
            <Route path="/booking/permintaan" element={<BookingRequest />} />
            <Route path="/thank-you" element={<ThankYou />} />
            <Route path="/blog" element={<Blog />} />
            <Route path="/blog/:slug" element={<BlogDetail />} />
            <Route path="/about" element={<About />} />
            <Route path="/contact" element={<Contact />} />
          </Route>

          {/* ERP APP (surface=app, login required) */}
          <Route path="/app/login" element={<Login />} />
          <Route path="/app" element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route index element={<Navigate to="/app/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="bookings" element={<RoleGuard section="bookings"><Bookings /></RoleGuard>} />
              <Route path="calendar" element={<RoleGuard section="calendar"><DepartureCalendar /></RoleGuard>} />
              <Route path="dispatch" element={<RoleGuard section="dispatch"><Dispatch /></RoleGuard>} />
              <Route path="driver-workspace" element={<RoleGuard section="driver-workspace"><DriverWorkspace /></RoleGuard>} />
              <Route path="vehicles" element={<RoleGuard section="vehicles"><Vehicles /></RoleGuard>} />
              <Route path="drivers" element={<RoleGuard section="drivers"><Drivers /></RoleGuard>} />
              <Route path="customers" element={<RoleGuard section="customers"><Customers /></RoleGuard>} />
              <Route path="masterdata" element={<RoleGuard section="masterdata"><MasterData /></RoleGuard>} />
              <Route path="crm" element={<RoleGuard section="crm"><Crm /></RoleGuard>} />
              <Route path="quotations" element={<RoleGuard section="quotations"><Quotations /></RoleGuard>} />
              <Route path="cms" element={<RoleGuard section="cms"><ContentManager /></RoleGuard>} />
              <Route path="media" element={<RoleGuard section="media"><MediaManager /></RoleGuard>} />
              <Route path="inbox" element={<RoleGuard section="inbox"><Inbox /></RoleGuard>} />
              <Route path="automation" element={<RoleGuard section="automation"><Automation /></RoleGuard>} />
              <Route path="users" element={<RoleGuard section="users"><Users /></RoleGuard>} />
              <Route path="gps" element={<RoleGuard section="gps"><GpsTracking /></RoleGuard>} />
              <Route path="finance" element={<RoleGuard section="finance"><Finance /></RoleGuard>} />
              <Route path="reports" element={<RoleGuard section="reports"><Reports /></RoleGuard>} />
              <Route path="maintenance" element={<RoleGuard section="maintenance"><Maintenance /></RoleGuard>} />
              <Route path="partners" element={<RoleGuard section="partners"><Partners /></RoleGuard>} />
              <Route path="integrations" element={<RoleGuard section="integrations"><Integrations /></RoleGuard>} />
              <Route path="tracking" element={<RoleGuard section="tracking"><TrackingHealth /></RoleGuard>} />
              <Route path="ads" element={<RoleGuard section="ads"><Ads /></RoleGuard>} />
              <Route path="landing" element={<RoleGuard section="landing"><LandingBuilder /></RoleGuard>} />
              <Route path="settings" element={<RoleGuard section="settings"><Settings /></RoleGuard>} />
              <Route path="documents" element={<RoleGuard section="documents"><Documents /></RoleGuard>} />
              <Route path="auditlog" element={<RoleGuard section="auditlog"><AuditLog /></RoleGuard>} />
            </Route>
          </Route>

          {/* PUBLIC TRACKING (share-link korporat, tanpa login) */}
          <Route path="/track/:token" element={<PublicTrack />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </AuthProvider>
  );
}

export default App;
