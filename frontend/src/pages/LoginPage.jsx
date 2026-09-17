import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import Button from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import Input from "../components/ui/Input";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm p-6">
        <h1 className="mb-4 text-xl font-semibold text-foreground">Đăng nhập EduTutor</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input
            type="password"
            placeholder="Mật khẩu"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Đang đăng nhập..." : "Đăng nhập"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-muted-foreground">
          Chưa có tài khoản?{" "}
          <Link to="/register" className="text-primary hover:underline">
            Đăng ký
          </Link>
        </p>
      </Card>
    </div>
  );
}
