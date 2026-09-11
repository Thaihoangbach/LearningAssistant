import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, RotateCcw, Save } from "lucide-react";
import { getProfile, resetProfile, updateProfile } from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Select from "../components/ui/Select";

const EFFECTIVE_LEVEL_LABEL = {
  beginner: "Người mới bắt đầu",
  advanced: "Nâng cao",
};

// Trả lời đúng câu "hệ thống đang coi tôi trình độ gì, và vì sao" — khác với
// ô dropdown ở trên vốn chỉ phản ánh preferred_level TỰ CHỌN, có thể trống
// trong khi effective_level (app/routers/profile.py) vẫn đang có giá trị suy
// ra từ mastery.
function EffectiveLevelStatus({ level, source }) {
  if (!level) {
    return (
      <p className="text-xs text-muted-foreground">
        Chưa có trình độ nào đang được áp dụng — câu trả lời dùng mức mặc định.
      </p>
    );
  }
  const label = EFFECTIVE_LEVEL_LABEL[level] || level;
  const reason =
    source === "declared"
      ? "do bạn tự chọn"
      : "hệ thống tự suy từ kết quả làm bài, bạn chưa từng tự chọn";
  return (
    <p className="text-xs text-muted-foreground">
      Hiện tại câu trả lời đang ở mức{" "}
      <span className="font-medium text-foreground">{label}</span> — {reason}.
    </p>
  );
}

export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [preferredLevel, setPreferredLevel] = useState("");
  const [learningGoal, setLearningGoal] = useState("");
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const load = () =>
    getProfile()
      .then((p) => {
        setProfile(p);
        setPreferredLevel(p.preferred_level || "");
        setLearningGoal(p.learning_goal || "");
      })
      .catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateProfile({
        preferredLevel: preferredLevel || null,
        learningGoal: learningGoal || null,
      });
      setSaved(true);
      // Nạp lại thay vì merge kết quả PUT — effective_level/effective_level_source
      // chỉ GET /profile mới tính, PUT không trả về.
      await load();
    } catch (e) {
      // Backend trả 400 kèm thông báo khi mục tiêu học tập khớp mẫu injection
      // (app/routers/profile.py) — đó là phản hồi có ý nghĩa với người dùng,
      // hiện nguyên văn chứ không giấu đi.
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    setError(null);
    setSaved(false);
    try {
      await resetProfile();
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">
            Cá nhân hoá câu trả lời
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <label htmlFor="profile-level" className="mb-1.5 block text-sm font-medium text-foreground">
              Trình độ mong muốn
            </label>
            <Select
              id="profile-level"
              value={preferredLevel}
              onChange={(e) => setPreferredLevel(e.target.value)}
            >
              <option value="">Để hệ thống tự suy từ kết quả làm bài</option>
              <option value="beginner">Người mới bắt đầu</option>
              <option value="advanced">Nâng cao</option>
            </Select>
            <p className="mt-1.5 text-xs text-muted-foreground">
              Dùng để chỉnh độ sâu câu trả lời và độ khó quiz/flashcard. Lưu ở đây thì không
              phải chọn lại mỗi lần hỏi.
            </p>
            {profile && (
              <div className="mt-1.5">
                <EffectiveLevelStatus level={profile.effective_level} source={profile.effective_level_source} />
              </div>
            )}
          </div>

          <div>
            <label htmlFor="profile-goal" className="mb-1.5 block text-sm font-medium text-foreground">
              Mục tiêu học tập
            </label>
            <Input
              id="profile-goal"
              placeholder="VD: Đang ôn nền tảng Học máy để chuẩn bị phỏng vấn"
              value={learningGoal}
              onChange={(e) => setLearningGoal(e.target.value)}
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Dùng làm bối cảnh khi AI trả lời. Không nhập deadline/số ngày ở đây — việc chia
              lịch ôn theo hạn thuộc trang Kế hoạch ôn tập.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={handleSave} loading={saving} className="shrink-0">
              <Save className="h-4 w-4" aria-hidden="true" />
              Lưu hồ sơ
            </Button>
            <Button variant="outline" onClick={handleReset} loading={resetting} className="shrink-0">
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Đặt lại trình độ &amp; mục tiêu đã lưu
            </Button>
            {saved && <span className="text-sm text-success">Đã lưu.</span>}
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      <Link
        to="/"
        className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-primary hover:underline"
      >
        Xem điểm thành thạo theo chủ đề
        <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>
    </div>
  );
}
