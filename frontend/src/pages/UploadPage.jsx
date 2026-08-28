import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, FileUp, Inbox, ListTree, Trash2 } from "lucide-react";
import {
  uploadDocument,
  listDocuments,
  deleteDocument,
  getDocumentOutline,
} from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import EmptyState from "../components/ui/EmptyState";
import StatusBadge from "../components/StatusBadge";

function DocumentOutline({ documentId }) {
  const [topics, setTopics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getDocumentOutline(documentId)
      .then((res) => setTopics(res.topics))
      .catch((e) => setError(e.message));
  }, [documentId]);

  if (error) return <p className="py-2 text-xs text-destructive">{error}</p>;
  if (topics === null) return <p className="py-2 text-xs text-muted-foreground">Đang tải dàn ý...</p>;
  if (topics.length === 0) {
    return (
      <p className="py-2 text-xs text-muted-foreground">
        Không rút được dàn ý từ tài liệu này — nó không có tiêu đề mục rõ ràng. Bạn vẫn hỏi
        đáp và tạo quiz bình thường được.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-1.5 py-2">
      {topics.map((t) => (
        <li key={`${t.order}-${t.title}`} className="flex items-center justify-between gap-3">
          <span className="min-w-0 truncate text-sm text-foreground">
            {t.title}
            <span className="ml-2 text-xs text-muted-foreground">{t.position_ref}</span>
          </span>
          {/* Đưa thẳng người dùng sang hỏi đáp với câu hỏi đã điền sẵn — thứ họ
              thiếu khi mở tài liệu mới là biết nên hỏi gì. */}
          <Link
            to={`/chat?q=${encodeURIComponent(`${t.title} là gì?`)}`}
            className="shrink-0 text-xs font-medium text-primary hover:underline"
          >
            Hỏi về mục này
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function UploadPage() {
  const [courseName, setCourseName] = useState("");
  const [file, setFile] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [openOutlineId, setOpenOutlineId] = useState(null);

  const refresh = async () => {
    try {
      setDocuments(await listDocuments());
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    refresh();
    // F1 AC: trạng thái xử lý cập nhật theo thời gian thực -> poll đơn giản mỗi 2s
    const interval = setInterval(refresh, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(file, courseName);
      setFile(null);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (documentId) => {
    if (!window.confirm("Xoá tài liệu này? Toàn bộ dữ liệu liên quan (chunk, embedding) sẽ bị xoá.")) return;
    setDeletingId(documentId);
    setError(null);
    try {
      await deleteDocument(documentId);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">Tải tài liệu mới</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleUpload} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label htmlFor="course-name" className="mb-1.5 block text-sm font-medium text-foreground">
                Tên môn học
              </label>
              <Input
                id="course-name"
                placeholder="VD: Cơ sở dữ liệu"
                value={courseName}
                onChange={(e) => setCourseName(e.target.value)}
              />
            </div>
            <div className="flex-1">
              <label htmlFor="file-input" className="mb-1.5 block text-sm font-medium text-foreground">
                Tệp PDF hoặc DOCX
              </label>
              <input
                id="file-input"
                type="file"
                accept=".pdf,.docx"
                onChange={(e) => setFile(e.target.files[0])}
                className="block w-full cursor-pointer text-sm text-foreground file:mr-3 file:h-11 file:cursor-pointer file:rounded-lg file:border-0 file:bg-primary/10 file:px-4 file:text-sm file:font-semibold file:text-primary hover:file:bg-primary/20"
              />
            </div>
            <Button type="submit" disabled={!file} loading={uploading} className="shrink-0">
              <FileUp className="h-4 w-4" aria-hidden="true" />
              {uploading ? "Đang tải lên..." : "Tải tài liệu"}
            </Button>
          </form>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">Danh sách tài liệu</CardTitle>
        </CardHeader>
        <CardContent>
          {documents.length === 0 ? (
            <EmptyState icon={Inbox} title="Chưa có tài liệu nào" description="Tải lên tài liệu đầu tiên ở trên để bắt đầu." />
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {documents.map((d) => (
                <li key={d.id} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{d.course_name || d.file_name}</p>
                      {d.course_name && (
                        <p className="truncate text-xs text-muted-foreground">{d.file_name}</p>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {d.status === "sẵn sàng" && (
                        <button
                          type="button"
                          onClick={() => setOpenOutlineId(openOutlineId === d.id ? null : d.id)}
                          className="flex cursor-pointer items-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          aria-expanded={openOutlineId === d.id}
                        >
                          {openOutlineId === d.id ? (
                            <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
                          ) : (
                            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
                          )}
                          <ListTree className="h-3.5 w-3.5" aria-hidden="true" />
                          Nội dung
                        </button>
                      )}
                      <StatusBadge status={d.status} reason={d.error_reason} />
                      <Button
                        type="button"
                        variant="destructive"
                        size="icon"
                        loading={deletingId === d.id}
                        onClick={() => handleDelete(d.id)}
                        aria-label={`Xoá ${d.file_name}`}
                      >
                        {deletingId !== d.id && <Trash2 className="h-4 w-4" aria-hidden="true" />}
                      </Button>
                    </div>
                  </div>
                  {openOutlineId === d.id && <DocumentOutline documentId={d.id} />}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
