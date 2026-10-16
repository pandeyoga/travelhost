import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Layers3, Loader2 } from "lucide-react";

export default function Login() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  if (!loading && user) return <Navigate to="/app/dashboard" replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      toast.success("Berhasil masuk");
      navigate("/app/dashboard", { replace: true });
    } catch (err) {
      const msg = err?.response?.data?.detail || "Gagal masuk. Periksa email/kata sandi.";
      setErrorMsg(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="app-shell flex min-h-screen items-center justify-center px-4"
      data-surface="app"
      data-testid="login-page"
    >
      <div className="w-full max-w-[400px]">
        <div className="mb-7 flex flex-col items-center text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-[13px] bg-[#0B0B0F] text-white">
            <Layers3 size={22} />
          </div>
          <h1 className="text-[22px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>RahazaTrans</h1>
          <p className="text-[13px] text-[#6B6B73]">Fleet Management Console</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-[18px] border border-[#E5E5EA] bg-white p-6 shadow-[0_10px_40px_rgba(20,28,45,0.08)]"
        >
          <div className="space-y-1.5">
            <Label htmlFor="email" className="text-[13px] font-semibold text-[#3C3C43]">Email</Label>
            <Input id="email" type="email" autoComplete="username" placeholder="nama@perusahaan.com"
              value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="login-email-input" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password" className="text-[13px] font-semibold text-[#3C3C43]">Kata Sandi</Label>
            <Input id="password" type="password" autoComplete="current-password" placeholder="••••••••"
              value={password} onChange={(e) => setPassword(e.target.value)} required data-testid="login-password-input" />
          </div>

          {errorMsg ? <p className="text-sm text-[#C62828]" data-testid="login-error">{errorMsg}</p> : null}

          <button type="submit" className="primary-button w-full" disabled={submitting} data-testid="login-submit-button">
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Masuk
          </button>

          {process.env.NODE_ENV !== "production" ? (
            <div className="rounded-[10px] bg-[#F5F6F8] p-3 text-xs text-[#6B6B73]">
              <p className="mb-1 font-semibold text-[#1C1C1E]">Akun demo (password: demo12345)</p>
              <p>owner@demo.local · ops@demo.local · driver@demo.local</p>
            </div>
          ) : null}
        </form>
      </div>
    </div>
  );
}
