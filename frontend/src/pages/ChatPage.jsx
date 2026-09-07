import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BookmarkPlus, BookOpen, History, Lightbulb, MessageCircle, Plus, Send } from "lucide-react";
import {
  askQuestion,
  getConversation,
  listConversations,
  saveFlashcardFromAnswer,
} from "../api";
import { Card } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import EmptyState from "../components/ui/EmptyState";
import AnswerWithCitations from "../components/AnswerWithCitations";
import CitationPanel from "../components/CitationPanel";
import SearchReport from "../components/SearchReport";
import { cn } from "../lib/cn";

function formatDate(isoString) {
  return new Date(isoString).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm bg-muted px-4 py-3">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" />
    </div>
  );
}

function MessageBubble({ message, onOpenSource, onAskAgain, onSaveCard }) {
  const isUser = message.role === "user";
  const sources = message.sources || [];

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("flex max-w-[85%] flex-col gap-1.5", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "rounded-br-sm bg-primary text-primary-foreground"
              : "rounded-bl-sm bg-muted text-foreground"
          )}
        >
          {isUser ? (
            message.content
          ) : (
            <AnswerWithCitations
              answer={message.content}
              sources={sources}
              onOpenSource={(i) => onOpenSource(sources[i])}
            />
          )}
        </div>

        {!isUser && message.searchReport && (
          <SearchReport
            report={message.searchReport}
            // Đoạn gần đúng chưa qua bước tính câu chống đỡ (nó không chống đỡ
            // câu trả lời nào cả) nên truyền danh sách rỗng để panel không tô sáng.
            onOpenNearMiss={(n) => onOpenSource({ ...n, supporting_sentences: [] })}
            onAskTopic={(t) => onAskAgain(`${t} là gì?`)}
          />
        )}

        {!isUser && message.isGrounded && (
          <div className="flex flex-wrap items-center gap-3 pl-1">
            {/* Cách người học thật sự nghĩ là "chỗ này khó quá", chứ không phải
                "tôi là trình độ beginner" — nên đây là một nút, không phải một
                ô chọn trình độ. Câu này khớp _SIMPLIFY_REQUEST_RE ở backend. */}
            <button
              type="button"
              onClick={() => onAskAgain(`Tôi chưa hiểu, giải thích đơn giản hơn giúp tôi: ${message.forQuestion || ""}`)}
              className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Lightbulb className="h-3.5 w-3.5" aria-hidden="true" />
              Giải thích dễ hiểu hơn
            </button>
            <button
              type="button"
              onClick={() => onSaveCard(message)}
              disabled={message.saved}
              className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors enabled:cursor-pointer enabled:hover:text-primary disabled:text-success focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <BookmarkPlus className="h-3.5 w-3.5" aria-hidden="true" />
              {message.saved ? "Đã lưu thành thẻ" : "Lưu thành thẻ ôn tập"}
            </button>
          </div>
        )}

        {!isUser && sources.length > 0 && (
          <ul className="flex flex-col gap-1 pl-1">
            {sources.map((s, j) => (
              <li key={j}>
                <button
                  type="button"
                  onClick={() => onOpenSource(s)}
                  className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <BookOpen className="h-3 w-3 shrink-0" aria-hidden="true" />
                  [{j + 1}] {s.document_name} — {s.position_ref}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ConversationList({ conversations, activeId, onSelect, error, loading }) {
  if (error) {
    return <p className="p-4 text-sm text-destructive">{error}</p>;
  }
  // Chờ lượt tải ĐẦU TIÊN xong mới quyết định hiện "Chưa có lịch sử" — trước
  // đây `conversations` khởi tạo `[]` nên EmptyState hiện ngay lúc mount rồi
  // mới nhảy sang danh sách thật khi fetch xong, tạo cảm giác "vừa mất hết
  // lịch sử rồi lại có" mỗi lần vào trang.
  if (loading) {
    return <p className="p-4 text-sm text-muted-foreground">Đang tải…</p>;
  }
  if (conversations.length === 0) {
    return (
      <div className="p-4">
        <EmptyState icon={History} title="Chưa có lịch sử" description="Các cuộc hội thoại đã hỏi sẽ hiện ở đây." />
      </div>
    );
  }
  return (
    <ul className="flex flex-col divide-y divide-border">
      {conversations.map((c) => (
        <li key={c.id}>
          <button
            type="button"
            onClick={() => onSelect(c.id)}
            className={cn(
              "block w-full px-4 py-3 text-left transition-colors hover:bg-muted",
              c.id === activeId && "bg-muted"
            )}
          >
            <p className="truncate text-sm font-medium text-foreground">
              {c.preview || "(cuộc hội thoại trống)"}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">{formatDate(c.created_at)}</p>
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(false);
  // Không có ô chọn trình độ ở đây nữa: người học nghĩ "chỗ này khó quá", chứ
  // không nghĩ "tôi là trình độ nâng cao". Trình độ được backend suy từ kết quả
  // làm bài (app/services/learner_context.py), còn muốn cố định thì đặt ở
  // trang Hồ sơ.
  const [openSource, setOpenSource] = useState(null);

  const [conversations, setConversations] = useState([]);
  const [listError, setListError] = useState(null);
  const [conversationsLoading, setConversationsLoading] = useState(true);

  // Tăng mỗi khi người dùng bắt đầu một PHIÊN hội thoại khác (bấm "Cuộc hội
  // thoại mới" hoặc chọn hội thoại khác trong lịch sử) trong lúc một câu hỏi
  // trước đó còn đang chờ trả lời. `askQuestion`/`getConversation` chụp lại
  // giá trị hiện tại lúc bắt đầu gọi; khi resolve, chỉ áp kết quả nếu giá trị
  // vẫn còn khớp — nếu không thì người dùng đã rời sang hội thoại khác, áp
  // thẳng sẽ làm tin nhắn/conversationId của phiên CŨ lẫn vào màn hình đang
  // xem, hoặc tệ hơn là đổi conversationId đang active sang một hội thoại
  // người dùng không còn chọn.
  const sessionTokenRef = useRef(0);

  const refreshConversations = async () => {
    try {
      setConversations(await listConversations());
      setListError(null);
    } catch (e) {
      setListError(e.message);
    } finally {
      setConversationsLoading(false);
    }
  };

  useEffect(() => {
    refreshConversations();
  }, []);

  // Điền sẵn câu hỏi khi người dùng bấm "Hỏi về mục này" từ dàn ý tài liệu.
  // Chỉ điền vào ô nhập chứ KHÔNG tự gửi — người dùng còn muốn sửa lại câu hỏi
  // trước khi hỏi.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    const prefilled = searchParams.get("q");
    if (prefilled) {
      setQuestion(prefilled);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const handleSelectConversation = async (id) => {
    if (id === conversationId) return;
    const token = ++sessionTokenRef.current;
    setLoading(true);
    try {
      const convo = await getConversation(id);
      if (sessionTokenRef.current !== token) return; // đã chuyển sang phiên khác trong lúc chờ
      setConversationId(convo.id);
      setMessages(
        convo.messages.map((m) => ({
          role: m.role,
          content: m.content,
          isGrounded: m.is_grounded,
          sources: m.sources,
        }))
      );
    } catch (e) {
      if (sessionTokenRef.current !== token) return;
      setMessages([{ role: "assistant", content: `Lỗi: ${e.message}`, isGrounded: false }]);
    } finally {
      if (sessionTokenRef.current === token) setLoading(false);
    }
  };

  const handleNewConversation = () => {
    sessionTokenRef.current += 1;
    setConversationId(null);
    setMessages([]);
    setLoading(false);
  };

  const handleSaveCard = async (index, message) => {
    const firstSource = (message.sources || [])[0];
    try {
      await saveFlashcardFromAnswer({
        // Mặt trước là câu hỏi, mặt sau là câu trả lời — đúng thứ người học
        // muốn nhớ lại về sau.
        front: message.forQuestion || "Câu hỏi đã lưu",
        back: message.content,
        sourceDocument: firstSource?.document_name,
        sourcePosition: firstSource?.position_ref,
      });
      setMessages((m) => m.map((msg, i) => (i === index ? { ...msg, saved: true } : msg)));
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: `Lỗi: ${e.message}`, isGrounded: false }]);
    }
  };

  const handleAskText = async (text) => {
    const trimmed = (text || "").trim();
    // Chặn gửi trùng: Input không tự chặn Enter khi đang loading (chỉ nút Gửi
    // có `disabled`), nên gõ nhanh rồi Enter 2 lần trước đây tạo ra 2 lượt gọi
    // askQuestion() chồng nhau — cả hai cùng đọc `conversationId` cũ (null cho
    // hội thoại mới), có thể sinh 2 conversation riêng ở backend cho 1 hội
    // thoại ở giao diện.
    if (loading || !trimmed) return;

    const token = ++sessionTokenRef.current;
    const askedInConversationId = conversationId;
    const isNewConversation = askedInConversationId === null;
    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setQuestion("");
    setLoading(true);

    try {
      const result = await askQuestion(trimmed, askedInConversationId);
      // Người dùng đã bấm "Cuộc hội thoại mới" hoặc chọn hội thoại khác trong
      // lúc chờ — câu trả lời này không còn thuộc về màn hình đang xem, áp
      // vào sẽ làm lẫn tin nhắn giữa 2 hội thoại hoặc đổi nhầm conversationId
      // đang active.
      if (sessionTokenRef.current !== token) return;
      setConversationId(result.conversation_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: result.answer,
          isGrounded: result.is_grounded,
          sources: result.sources,
          // Giữ lại câu hỏi đã sinh ra câu trả lời này, để nút "lưu thành thẻ"
          // dùng nó làm mặt trước và nút "giải thích dễ hiểu hơn" hỏi lại đúng ý.
          forQuestion: trimmed,
          // Chỉ giữ báo cáo tìm kiếm khi hệ thống TỪ CHỐI — lúc trả lời được
          // thì báo cáo không mang thông tin gì người dùng cần.
          searchReport: result.abstained ? result.search_report : null,
        },
      ]);
      if (isNewConversation) {
        await refreshConversations();
      }
    } catch (e) {
      if (sessionTokenRef.current !== token) return;
      setMessages((m) => [...m, { role: "assistant", content: `Lỗi: ${e.message}`, isGrounded: false }]);
    } finally {
      if (sessionTokenRef.current === token) setLoading(false);
    }
  };

  const handleAsk = (e) => {
    e.preventDefault();
    handleAskText(question);
  };

  return (
    <div className="flex h-[calc(100dvh-9.5rem)] gap-4">
      <Card className="flex w-72 shrink-0 flex-col overflow-hidden">
        <div className="border-b border-border p-3">
          <Button type="button" variant="outline" className="w-full" onClick={handleNewConversation}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Cuộc hội thoại mới
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <ConversationList
            conversations={conversations}
            activeId={conversationId}
            onSelect={handleSelectConversation}
            error={listError}
            loading={conversationsLoading}
          />
        </div>
      </Card>

      <Card className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4 sm:p-5">
          {messages.length === 0 ? (
            <EmptyState
              icon={MessageCircle}
              title="Hỏi đáp tài liệu"
              description="Đặt câu hỏi về nội dung tài liệu đã tải lên, câu trả lời sẽ kèm nguồn trích dẫn."
            />
          ) : (
            <div className="flex flex-col gap-4">
              {messages.map((m, i) => (
                <MessageBubble
                  key={i}
                  message={m}
                  onOpenSource={setOpenSource}
                  onAskAgain={handleAskText}
                  onSaveCard={(msg) => handleSaveCard(i, msg)}
                />
              ))}
              {loading && (
                <div className="flex justify-start">
                  <TypingIndicator />
                </div>
              )}
            </div>
          )}
        </div>

        <form onSubmit={handleAsk} className="flex items-center gap-2 border-t border-border p-3 sm:p-4">
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Hỏi về nội dung tài liệu đã tải..."
            className="flex-1"
            disabled={loading}
          />
          <Button type="submit" disabled={!question.trim()} loading={loading} size="icon" aria-label="Gửi câu hỏi">
            <Send className="h-4 w-4" aria-hidden="true" />
          </Button>
        </form>
      </Card>

      <CitationPanel source={openSource} onClose={() => setOpenSource(null)} />
    </div>
  );
}
