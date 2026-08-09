import { BrowserRouter, Route, Routes, Outlet, useLocation } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import ChatPage from "./pages/ChatPage";
import QuizPage from "./pages/QuizPage";

const PAGE_TITLES = {
  "/": "Tổng quan",
  "/documents": "Tài liệu học tập",
  "/chat": "Hỏi đáp tài liệu",
  "/quiz": "Quiz tự kiểm tra",
};

function Layout() {
  const location = useLocation();
  const title = PAGE_TITLES[location.pathname] || "EduTutor";
  return (
    <AppShell title={title}>
      <Outlet />
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
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
