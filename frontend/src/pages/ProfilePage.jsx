import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { getProfile, updateProfile } from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Select from "../components/ui/Select";
import Badge from "../components/ui/Badge";

function TopicBadges({ names, emptyText }) {
  if (!names || names.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyText}</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {names.map((n) => (
        <Badge key={n}>{n}</Badge>
      ))}
    </div>
  );
}

export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [preferredLevel, setPreferredLevel] = useState("");
  const [learningGoal, setLearningGoal] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getProfile()
      .then((p) => {
        setProfile(p);
        setPreferredLevel(p.preferred_level || "");
        setLearningGoal(p.learning_goal || "");
      })
      .catch((e) => setError(e.message));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const res = await updateProfile({
        preferredLevel: preferredLevel || null,
        learningGoal: learningGoal || null,
      });
      setProfile((p) => ({ ...p, ...res }));
      setSaved(true);
    } catch (e) {
      // Backend trả 400 kèm thông báo khi mục tiêu học tập khớp mẫu injection
      // (app/routers/profile.py) — đó là phản hồi có ý nghĩa với người dùng,
      // hiện nguyên văn chứ không giấu đi.
      setError(e.message);
    } finally {
      setSaving(false);
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
              Lưu ở đây thì không phải chọn lại mỗi lần hỏi.
            </p>
          </div>

          <div>
            <label htmlFor="profile-goal" className="mb-1.5 block text-sm font-medium text-foreground">
              Mục tiêu học tập
            </label>
            <Input
              id="profile-goal"
              placeholder="VD: Ôn thi cuối kỳ môn Học máy trong 2 tuần"
              value={learningGoal}
              onChange={(e) => setLearningGoal(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-3">
            <Button onClick={handleSave} loading={saving} className="shrink-0">
              <Save className="h-4 w-4" aria-hidden="true" />
              Lưu hồ sơ
            </Button>
            {saved && <span className="text-sm text-success">Đã lưu.</span>}
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">
            Tiến độ suy ra từ kết quả làm bài
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {profile === null ? (
            <p className="text-sm text-muted-foreground">Đang tải…</p>
          ) : (
            <>
              <div>
                <p className="mb-2 text-sm font-medium text-foreground">Chủ đề còn yếu</p>
                <TopicBadges
                  names={profile?.weak_topics}
                  emptyText="Chưa có chủ đề nào bị đánh giá là yếu."
                />
              </div>
              <div>
                <p className="mb-2 text-sm font-medium text-foreground">Chủ đề đã nắm vững</p>
                <TopicBadges
                  names={profile?.mastered_topics}
                  emptyText="Chưa có chủ đề nào đạt mức thành thạo tốt."
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Hai danh sách này tính lại từ điểm thành thạo mỗi lần mở trang, không phải do bạn tự
                khai — nên chúng luôn phản ánh kết quả làm bài gần nhất.
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
