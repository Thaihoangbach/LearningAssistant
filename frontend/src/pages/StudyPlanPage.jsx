import { useState } from "react";
import { CalendarDays, Wand2 } from "lucide-react";
import { getStudyPlan } from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Select from "../components/ui/Select";
import EmptyState from "../components/ui/EmptyState";

export default function StudyPlanPage() {
  const [days, setDays] = useState(7);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getStudyPlan(days);
      setPlan(res.days);
    } catch (e) {
      setError(e.message);
      setPlan(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">
            Chia lịch ôn tập theo thời hạn
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="w-48">
              <label htmlFor="plan-days" className="mb-1.5 block text-sm font-medium text-foreground">
                Số ngày còn lại
              </label>
              <Select id="plan-days" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                {[1, 3, 5, 7, 10, 14, 21, 30].map((n) => (
                  <option key={n} value={n}>
                    {n} ngày
                  </option>
                ))}
              </Select>
            </div>
            <Button onClick={handleGenerate} loading={loading} className="shrink-0">
              <Wand2 className="h-4 w-4" aria-hidden="true" />
              {loading ? "Đang chia lịch..." : "Lập kế hoạch"}
            </Button>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Kế hoạch được tính lại từ đầu mỗi lần bấm, dựa trên điểm thành thạo mới nhất —
            chủ đề yếu hoặc chưa học được xếp lên trước.
          </p>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {plan === null ? (
        <EmptyState
          icon={CalendarDays}
          title="Chưa có kế hoạch"
          description="Chọn số ngày còn lại tới hạn và bấm Lập kế hoạch."
        />
      ) : plan.length === 0 ? (
        <EmptyState
          icon={CalendarDays}
          title="Chưa đủ dữ liệu để chia lịch"
          description="Hệ thống cần biết bạn mạnh yếu ở đâu trước. Hãy làm một quiz để có điểm thành thạo, rồi quay lại đây."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {plan.map((d) => (
            <Card key={d.day}>
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-foreground">Ngày {d.day}</CardTitle>
              </CardHeader>
              <CardContent>
                {d.topics.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Nghỉ / ôn tự do</p>
                ) : (
                  <ul className="flex flex-col gap-1.5">
                    {d.topics.map((t) => (
                      <li key={t} className="text-sm text-foreground">
                        • {t}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
