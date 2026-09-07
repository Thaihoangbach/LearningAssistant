import { BrowserRouter, Route, Routes, Outlet, useLocation } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import ErrorBoundary from "./components/ErrorBoundary";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import ChatPage from "./pages/ChatPage";
import QuizPage from "./pages/QuizPage";
import FlashcardsPage from "./pages/FlashcardsPage";
import StudyPlanPage from "./pages/StudyPlanPage";
import ProfilePage from "./pages/ProfilePage";
import MemoryPage from "./pages/MemoryPage";

const PAGE_TITLES = {
  "/": "Tổng quan",
  "/documents": "Tài liệu học tập",
  "/chat": "Hỏi đáp tài liệu",
  "/quiz": "Quiz tự kiểm tra",
  "/flashcards": "Flashcard ôn tập",
  "/study-plan": "Kế hoạch ôn tập",
  "/profile": "Hồ sơ học tập",
  "/memory": "Ký ức hệ thống",
};

function Layout() {
  const location = useLocation();
  const title = PAGE_TITLES[location.pathname] || "EduTutor";
  return (
    <AppShell title={title}>
      {/* `key` đổi theo route -> đổi trang tự dựng lại ErrorBoundary (React
          coi là component mới), nên rời khỏi trang lỗi rồi quay lại không
          cần nút "thử lại" riêng gọi lại đúng logic đã crash. */}
      <ErrorBoundary key={location.pathname}>
        <Outlet />
      </ErrorBoundary>
    </AppShell>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/documents" element={<UploadPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/quiz" element={<QuizPage />} />
          <Route path="/flashcards" element={<FlashcardsPage />} />
          <Route path="/study-plan" element={<StudyPlanPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/memory" element={<MemoryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
