import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import Button from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import Input from "../components/ui/Input";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, displayName);
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
        <h1 className="mb-4 text-xl font-semibold text-foreground">Tạo tài khoản EduTutor</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            placeholder="Tên hiển thị"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
          <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input
            type="password"
            placeholder="Mật khẩu (8-64 ký tự)"
            minLength={8}
            maxLength={64}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Đang tạo tài khoản..." : "Đăng ký"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-muted-foreground">
          Đã có tài khoản?{" "}
          <Link to="/login" className="text-primary hover:underline">
            Đăng nhập
          </Link>
        </p>
      </Card>
    </div>
  );
}
