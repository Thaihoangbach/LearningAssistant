import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, GraduationCap, Plus } from "lucide-react";
import {
  deleteCourseExamDate,
  getStudyPlan,
  listCourses,
  markTopicReviewed,
  setCourseExamDate,
} from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import Modal from "../components/ui/Modal";
import { cn } from "../lib/cn";

const WEEKDAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
const MONTH_LABELS = [
  "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6",
  "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12",
];

function startOfDay(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

function addDays(date, n) {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}

function toDateKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatDayLabel(date) {
  return `${WEEKDAY_LABELS[(date.getDay() + 6) % 7]}, ${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()}`;
}

// Backend neo "ngày 1" của kế hoạch vào date.today() phía SERVER (chạy UTC),
// không phải ngày lịch local của trình duyệt. Dùng riêng mốc này để quy đổi
// plan[i].day -> ngày thật, tách biệt với `today` (local, dùng cho highlight
// ô hôm nay và các gate khác) — xem finding #5 của đợt review cuối.
function todayUTC() {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
}

// Lưới 6 hàng x 7 cột (Thứ 2 -> Chủ nhật) phủ đủ tháng chứa `monthDate`.
function buildMonthMatrix(monthDate) {
  const firstOfMonth = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
  // getDay(): 0=CN..6=T7 -> quy về 0=T2..6=CN để tuần bắt đầu từ Thứ Hai.
  const firstWeekday = (firstOfMonth.getDay() + 6) % 7;
  const gridStart = addDays(firstOfMonth, -firstWeekday);

  const weeks = [];
  let cursor = gridStart;
  for (let w = 0; w < 6; w++) {
    const week = [];
    for (let d = 0; d < 7; d++) {
      week.push(cursor);
      cursor = addDays(cursor, 1);
    }
    weeks.push(week);
  }
  return weeks;
}

function groupTopicsByCourse(topics) {
  const order = [];
  const byCourse = new Map();
  for (const t of topics) {
    const key = t.course_name || "";
    if (!byCourse.has(key)) {
      byCourse.set(key, { course_name: t.course_name, count: 0 });
      order.push(key);
    }
    byCourse.get(key).count += 1;
  }
  return order.map((k) => byCourse.get(k));
}

// Chủ đề đã ôn hôm nay chìm xuống cuối danh sách thay vì biến mất — người
// dùng vẫn thấy mình đã ôn những gì trong ngày (yêu cầu người dùng).
function sortTopicsForDisplay(topics) {
  return [...topics].sort((a, b) => {
    if (a.reviewed_today === b.reviewed_today) return 0;
    return a.reviewed_today ? 1 : -1;
  });
}

function topicActionHref(base, topic) {
  const params = new URLSearchParams({ topic: topic.name });
  if (topic.document_id) params.set("document", topic.document_id);
  return `${base}?${params}`;
}

export default function StudyPlanPage() {
  const [courses, setCourses] = useState([]);
  const [coursesLoading, setCoursesLoading] = useState(true);
  const [selectedCourses, setSelectedCourses] = useState([]);
  const hasInitializedSelection = useRef(false);

  const [plan, setPlan] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [error, setError] = useState(null);
  const planRequestId = useRef(0);

  const today = useMemo(() => startOfDay(new Date()), []);
  // Mốc UTC riêng cho việc quy đổi ngày kế hoạch -> ngày lịch (finding #5) —
  // KHÔNG dùng cho highlight/gate theo ngày local, những chỗ đó vẫn dùng `today`.
  const planAnchor = useMemo(() => todayUTC(), []);
  const [viewMonth, setViewMonth] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));
  const [selectedDate, setSelectedDate] = useState(null);

  const [removingExam, setRemovingExam] = useState(null); // course_name đang xoá, hoặc null
  const [reviewingTopic, setReviewingTopic] = useState(null); // key topic đang đánh dấu, hoặc null

  // Popup đặt ngày thi (chọn nhiều môn cùng lúc) — tách biệt hoàn toàn khỏi
  // khung chi tiết ngày phía dưới, mở được trên BẤT KỲ ngày nào (kể cả ngày
  // đã có chủ đề/ngày thi của môn khác), theo đúng yêu cầu người dùng.
  const [examPopupDate, setExamPopupDate] = useState(null);
  const [examPopupSelected, setExamPopupSelected] = useState([]);
  const [examPopupSaving, setExamPopupSaving] = useState(false);

  const loadCourses = async () => {
    setError(null);
    try {
      const res = await listCourses();
      setCourses(res.courses);
      if (!hasInitializedSelection.current) {
        hasInitializedSelection.current = true;
        setSelectedCourses(res.courses.filter((c) => c.exam_date).map((c) => c.course_name));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setCoursesLoading(false);
    }
  };

  useEffect(() => {
    loadCourses();
  }, []);

  const loadPlan = async () => {
    setError(null);
    const requestId = ++planRequestId.current;
    if (selectedCourses.length === 0) {
      setPlan([]);
      return;
    }
    setPlanLoading(true);
    try {
      const res = await getStudyPlan(selectedCourses);
      if (requestId !== planRequestId.current) return;
      setPlan(res.days);
    } catch (e) {
      if (requestId !== planRequestId.current) return;
      // Không setPlan([]) ở đây — giữ nguyên kế hoạch đã tải thành công trước
      // đó (vd các môn khác vẫn hợp lệ) khi một request bị lỗi (vd chọn nhầm
      // môn chưa đặt ngày thi); banner lỗi vẫn hiển thị để báo nguyên nhân.
      setError(e.message);
    } finally {
      if (requestId === planRequestId.current) setPlanLoading(false);
    }
  };

  const refreshAll = async () => {
    await loadCourses();
    await loadPlan();
  };

  useEffect(() => {
    if (!coursesLoading) loadPlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coursesLoading, selectedCourses]);

  const topicsByDateKey = useMemo(() => {
    const map = new Map();
    if (!plan) return map;
    for (const d of plan) {
      map.set(toDateKey(addDays(planAnchor, d.day - 1)), d.topics);
    }
    return map;
  }, [plan, planAnchor]);

  const examDateKeys = useMemo(() => {
    const map = new Map(); // dateKey -> course_name[]
    for (const c of courses) {
      if (!c.exam_date) continue;
      const list = map.get(c.exam_date) || [];
      list.push(c.course_name);
      map.set(c.exam_date, list);
    }
    return map;
  }, [courses]);

  const toggleCourse = (name) => {
    setSelectedCourses((prev) =>
      prev.includes(name) ? prev.filter((c) => c !== name) : [...prev, name]
    );
  };

  const weeks = useMemo(() => buildMonthMatrix(viewMonth), [viewMonth]);

  const handleDayClick = (date) => {
    setSelectedDate((prev) => (prev && toDateKey(prev) === toDateKey(date) ? null : date));
  };

  const openExamPopup = (date) => {
    setExamPopupDate(date);
    setExamPopupSelected([]);
  };

  const closeExamPopup = () => {
    setExamPopupDate(null);
    setExamPopupSelected([]);
  };

  const toggleExamPopupCourse = (name) => {
    setExamPopupSelected((prev) =>
      prev.includes(name) ? prev.filter((c) => c !== name) : [...prev, name]
    );
  };

  const handleApplyExamPopup = async () => {
    if (!examPopupDate || examPopupSelected.length === 0) return;
    setExamPopupSaving(true);
    setError(null);
    try {
      const dateKey = toDateKey(examPopupDate);
      for (const courseName of examPopupSelected) {
        await setCourseExamDate(courseName, dateKey);
      }
      // Mọi môn vừa được đặt ngày thi phải vào phạm vi kế hoạch, nếu không
      // chủ đề của chúng sẽ không hiện dù ngày thi đã lưu thành công.
      setSelectedCourses((prev) => {
        const merged = new Set(prev);
        for (const c of examPopupSelected) merged.add(c);
        return [...merged];
      });
      closeExamPopup();
      await refreshAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setExamPopupSaving(false);
    }
  };

  const handleRemoveExamDate = async (courseName) => {
    setRemovingExam(courseName);
    setError(null);
    try {
      await deleteCourseExamDate(courseName);
      // Môn vừa mất ngày thi phải ra khỏi phạm vi kế hoạch, nếu không
      // getStudyPlan() sẽ 400 vì thiếu ngày thi và xoá sạch lưới của MỌI môn
      // khác đang chọn (finding #1). Bỏ khỏi selectedCourses tự kích hoạt lại
      // effect loadPlan bên dưới — không cần gọi loadPlan() ở đây.
      setSelectedCourses((prev) => prev.filter((c) => c !== courseName));
      await loadCourses();
    } catch (e) {
      setError(e.message);
    } finally {
      setRemovingExam(null);
    }
  };

  const handleMarkReviewed = async (topic) => {
    const key = `${topic.course_name || ""}::${topic.name}`;
    setReviewingTopic(key);
    setError(null);
    try {
      await markTopicReviewed(topic.name, topic.course_name);
      await refreshAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setReviewingTopic(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">
            Môn học trong kế hoạch
          </CardTitle>
        </CardHeader>
        <CardContent>
          {coursesLoading ? (
            <p className="text-sm text-muted-foreground">Đang tải danh sách môn học…</p>
          ) : courses.length === 0 ? (
            <EmptyState
              icon={GraduationCap}
              title="Chưa có môn học nào"
              description="Tải tài liệu và điền tên môn học ở trang Tài liệu để bắt đầu."
            />
          ) : (
            <div className="flex flex-wrap gap-2">
              {courses.map((c) => {
                const active = selectedCourses.includes(c.course_name);
                return (
                  <button
                    key={c.course_name}
                    type="button"
                    onClick={() => toggleCourse(c.course_name)}
                    className={cn(
                      "flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full border px-3 text-sm font-medium transition-colors",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border text-muted-foreground hover:bg-muted"
                    )}
                  >
                    {c.course_name}
                    {!c.exam_date && (
                      <span className="text-xs font-normal opacity-70">(chưa đặt ngày thi)</span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-semibold text-foreground">
              {MONTH_LABELS[viewMonth.getMonth()]} {viewMonth.getFullYear()}
            </CardTitle>
            <div className="flex items-center gap-1">
              <button
                type="button"
                aria-label="Tháng trước"
                onClick={() => setViewMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))}
                className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label="Tháng sau"
                onClick={() => setViewMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))}
                className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {planLoading && <p className="mb-3 text-xs text-muted-foreground">Đang tính lại kế hoạch…</p>}
          <div className="grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-border bg-border text-xs">
            {WEEKDAY_LABELS.map((w) => (
              <div key={w} className="bg-muted px-2 py-1.5 text-center font-medium text-muted-foreground">
                {w}
              </div>
            ))}
            {weeks.flat().map((date) => {
              const dateKey = toDateKey(date);
              const inMonth = date.getMonth() === viewMonth.getMonth();
              const isToday = dateKey === toDateKey(today);
              const isPast = date < today;
              const isSelected = selectedDate && dateKey === toDateKey(selectedDate);
              const dayTopics = topicsByDateKey.get(dateKey) || [];
              const chips = groupTopicsByCourse(dayTopics);
              const exams = examDateKeys.get(dateKey) || [];
              const overflow = chips.length > 2 ? chips.length - 2 : 0;

              return (
                <div
                  key={dateKey}
                  className={cn(
                    "relative flex min-h-24 flex-col bg-card p-1.5",
                    !inMonth && "opacity-40",
                    isSelected && "ring-2 ring-inset ring-primary"
                  )}
                >
                  <button
                    type="button"
                    onClick={() => handleDayClick(date)}
                    className="flex flex-1 cursor-pointer flex-col items-stretch gap-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                  >
                    <span
                      className={cn(
                        "self-start rounded-full px-1.5 text-[11px] font-medium",
                        isToday ? "bg-primary text-primary-foreground" : "text-foreground"
                      )}
                    >
                      {date.getDate()}
                    </span>
                    {exams.length > 0 && (
                      <span className="truncate rounded bg-destructive/15 px-1 py-0.5 text-[10px] font-medium text-destructive">
                        Thi: {exams.join(", ")}
                      </span>
                    )}
                    {chips.slice(0, 2).map((c) => (
                      <span
                        key={c.course_name || "khac"}
                        className="truncate rounded bg-primary/10 px-1 py-0.5 text-[10px] font-medium text-primary"
                      >
                        {c.course_name || "Khác"} · {c.count}
                      </span>
                    ))}
                    {overflow > 0 && (
                      <span className="text-[10px] text-muted-foreground">+{overflow} khác</span>
                    )}
                  </button>
                  {!isPast && (
                    <button
                      type="button"
                      aria-label="Đặt ngày thi cho ngày này"
                      onClick={() => openExamPopup(date)}
                      className="absolute right-1 top-1 flex h-5 w-5 cursor-pointer items-center justify-center rounded-full bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Plus className="h-3 w-3" aria-hidden="true" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {selectedDate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              {formatDayLabel(selectedDate)}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {(examDateKeys.get(toDateKey(selectedDate)) || []).map((courseName) => (
              <div
                key={courseName}
                className="flex items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2"
              >
                <span className="text-sm font-medium text-destructive">Ngày thi: {courseName}</span>
                <Button
                  variant="destructive"
                  size="sm"
                  loading={removingExam === courseName}
                  onClick={() => handleRemoveExamDate(courseName)}
                >
                  Xoá
                </Button>
              </div>
            ))}
            {sortTopicsForDisplay(topicsByDateKey.get(toDateKey(selectedDate)) || []).map((topic) => {
              const key = `${topic.course_name || ""}::${topic.name}`;
              return (
                <div
                  key={key}
                  className={cn(
                    "flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between",
                    topic.reviewed_today && "bg-muted/40 opacity-70"
                  )}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{topic.name}</p>
                    {topic.course_name && (
                      <p className="truncate text-xs text-muted-foreground">{topic.course_name}</p>
                    )}
                  </div>
                  {topic.reviewed_today ? (
                    <span className="flex shrink-0 items-center gap-1.5 text-sm font-medium text-success">
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                      Đã ôn xong
                    </span>
                  ) : (
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Link
                        to={topicActionHref("/quiz", topic)}
                        className="flex h-9 items-center rounded-lg border border-border px-3 text-sm font-medium text-foreground hover:bg-muted"
                      >
                        Làm quiz
                      </Link>
                      <Link
                        to={topicActionHref("/flashcards", topic)}
                        className="flex h-9 items-center rounded-lg border border-border px-3 text-sm font-medium text-foreground hover:bg-muted"
                      >
                        Ôn flashcard
                      </Link>
                      {toDateKey(selectedDate) === toDateKey(today) && (
                        <Button
                          variant="secondary"
                          size="sm"
                          loading={reviewingTopic === key}
                          onClick={() => handleMarkReviewed(topic)}
                        >
                          Đã ôn xong
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
            {(topicsByDateKey.get(toDateKey(selectedDate)) || []).length === 0 &&
              (examDateKeys.get(toDateKey(selectedDate)) || []).length === 0 && (
                <p className="text-sm text-muted-foreground">Chưa có gì trong ngày này.</p>
              )}
          </CardContent>
        </Card>
      )}

      {!coursesLoading && courses.length > 0 && selectedCourses.length === 0 && (
        <EmptyState
          icon={CalendarDays}
          title="Chưa chọn môn nào"
          description="Chọn ít nhất một môn ở trên để xem kế hoạch ôn tập."
        />
      )}

      <Modal
        open={!!examPopupDate}
        onClose={closeExamPopup}
        title={examPopupDate ? `Đặt ngày thi — ${formatDayLabel(examPopupDate)}` : ""}
      >
        {courses.length === 0 ? (
          <p className="text-sm text-muted-foreground">Chưa có môn học nào.</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex max-h-60 flex-col gap-1 overflow-y-auto">
              {courses.map((c) => (
                <label
                  key={c.course_name}
                  className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground hover:bg-muted"
                >
                  <input
                    type="checkbox"
                    checked={examPopupSelected.includes(c.course_name)}
                    onChange={() => toggleExamPopupCourse(c.course_name)}
                    className="h-4 w-4 cursor-pointer rounded border-border"
                  />
                  {c.course_name}
                </label>
              ))}
            </div>
            <Button
              disabled={examPopupSelected.length === 0}
              loading={examPopupSaving}
              onClick={handleApplyExamPopup}
            >
              Đặt làm ngày thi
            </Button>
          </div>
        )}
      </Modal>
    </div>
  );
}
