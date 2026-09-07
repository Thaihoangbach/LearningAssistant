import { Component } from "react";
import { AlertTriangle } from "lucide-react";
import Button from "./ui/Button";

// Không có error boundary nào trong app trước đây — mọi trang tin tưởng
// tuyệt đối vào đúng hình dạng JSON backend trả về (vd
// `const { topics, summary } = mastery;` ở DashboardPage khi `mastery` lỡ là
// null/thiếu trường). Một lỗi render bất kỳ ở BẤT KỲ trang nào làm React gỡ
// toàn bộ cây, kể cả sidebar/topbar — người dùng thấy màn hình trắng, không
// có cách nào quay lại ngoài tải lại trang.
//
// Đặt boundary quanh MỖI trang (bọc <Outlet/> trong App.jsx, key theo
// pathname) thay vì bọc toàn bộ <App/> — một trang lỗi vẫn giữ được
// sidebar/topbar để người dùng bấm sang trang khác, và đổi route tự tạo lại
// component (key thay đổi) nên không cần nút "thử lại" gọi lại chính trang
// đã lỗi.
export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("Lỗi không xử lý được ở trang:", error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-destructive/40 bg-destructive/5 p-10 text-center">
        <AlertTriangle className="h-8 w-8 text-destructive" aria-hidden="true" />
        <p className="font-semibold text-foreground">Trang này gặp lỗi không mong muốn.</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          Dữ liệu trả về có thể không đúng định dạng trang đang chờ. Thử tải lại, hoặc chuyển
          sang một trang khác ở thanh bên.
        </p>
        <Button type="button" variant="outline" onClick={() => window.location.reload()}>
          Tải lại trang
        </Button>
      </div>
    );
  }
}
