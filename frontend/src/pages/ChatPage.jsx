import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BookOpen, History, MessageCircle, Plus, Send } from "lucide-react";
import { askQuestion, getConversation, listConversations } from "../api";
import { Card } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Select from "../components/ui/Select";
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

function MessageBubble({ message, onOpenSource }) {
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
          />
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

function ConversationList({ conversations, activeId, onSelect, error }) {
  if (error) {
    return <p className="p-4 text-sm text-destructive">{error}</p>;
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
  const [level, setLevel] = useState(""); // "" = để backend tự quyết theo hồ sơ
  const [openSource, setOpenSource] = useState(null);

  const [conversations, setConversations] = useState([]);
  const [listError, setListError] = useState(null);

  const refreshConversations = async () => {
    try {
      setConversations(await listConversations());
      setListError(null);
    } catch (e) {
      setListError(e.message);
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
    setLoading(true);
    try {
      const convo = await getConversation(id);
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
      setMessages([{ role: "assistant", content: `Lỗi: ${e.message}`, isGrounded: false }]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewConversation = () => {
    setConversationId(null);
    setMessages([]);
  };

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    const isNewConversation = conversationId === null;
    const userMessage = { role: "user", content: question };
    setMessages((m) => [...m, userMessage]);
    setQuestion("");
    setLoading(true);

    try {
      const result = await askQuestion(question, conversationId, level);
      setConversationId(result.conversation_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: result.answer,
          isGrounded: result.is_grounded,
          sources: result.sources,
          // Chỉ giữ báo cáo tìm kiếm khi hệ thống TỪ CHỐI — lúc trả lời được
          // thì báo cáo không mang thông tin gì người dùng cần.
          searchReport: result.abstained ? result.search_report : null,
        },
      ]);
      if (isNewConversation) {
        await refreshConversations();
      }
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: `Lỗi: ${e.message}`, isGrounded: false }]);
    } finally {
      setLoading(false);
    }
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
                <MessageBubble key={i} message={m} onOpenSource={setOpenSource} />
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
          <Select
            aria-label="Trình độ trả lời"
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="w-36 shrink-0"
          >
            <option value="">Tự động</option>
            <option value="beginner">Người mới</option>
            <option value="advanced">Nâng cao</option>
          </Select>
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Hỏi về nội dung tài liệu đã tải..."
            className="flex-1"
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
