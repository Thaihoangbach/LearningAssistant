const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";

// user_id tạm thời cố định cho walking skeleton — F5 (đăng nhập thật) chưa làm ở bước này.
export const CURRENT_USER_ID = "demo-user";

// Backend tra loi dang {"detail": "..."} — nem nguyen chuoi JSON ra man hinh
// se cho nguoi hoc thay mot thong bao ky thuat vo nghia. Boc lay `detail`,
// vi cac thong bao do (vd guardrail chan, tai lieu chua san sang) duoc viet
// cho nguoi dung doc.
async function raiseFriendlyError(res) {
  const raw = await res.text();

  let detail = null;
  try {
    detail = JSON.parse(raw)?.detail ?? null;
  } catch {
    // Không phải JSON (vd lỗi tầng proxy) — dùng nguyên văn phía dưới.
  }

  const message =
    typeof detail === "string" && detail.trim() ? detail : raw.trim() || `Lỗi ${res.status}`;
  throw new Error(message);
}


export async function uploadDocument(file, courseName) {
  const form = new FormData();
  form.append("file", file);
  const url = `${API_BASE}/documents?user_id=${CURRENT_USER_ID}&course_name=${encodeURIComponent(courseName || "")}`;
  const res = await fetch(url, { method: "POST", body: form });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function listDocuments() {
  const res = await fetch(`${API_BASE}/documents?user_id=${CURRENT_USER_ID}`);
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function deleteDocument(documentId) {
  const res = await fetch(`${API_BASE}/documents/${documentId}?user_id=${CURRENT_USER_ID}`, {
    method: "DELETE",
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function generateQuiz(documentId, topicName, numQuestions = 5, difficulty) {
  const res = await fetch(`${API_BASE}/quiz/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      document_id: documentId,
      topic_name: topicName || null,
      num_questions: numQuestions,
      // Không gửi difficulty khi người dùng để "Tự động" — backend sẽ dùng
      // trình độ đã lưu hoặc suy từ mastery (app/learner_context.py).
      ...(difficulty ? { difficulty } : {}),
    }),
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function submitAttempt(quizItemId, selectedAnswer) {
  const res = await fetch(`${API_BASE}/quiz/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      quiz_item_id: quizItemId,
      selected_answer: selectedAnswer,
    }),
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function getMastery() {
  const res = await fetch(`${API_BASE}/mastery?user_id=${CURRENT_USER_ID}`);
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function getMistakes(limit = 20) {
  const res = await fetch(
    `${API_BASE}/mastery/mistakes?user_id=${CURRENT_USER_ID}&limit=${limit}`
  );
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function askQuestion(question, conversationId, level) {
  const res = await fetch(`${API_BASE}/chat/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      question,
      conversation_id: conversationId || null,
      // Không gửi level khi người dùng để "Tự động" — backend sẽ dùng
      // preference đã lưu hoặc suy từ mastery (app/learner_context.py).
      ...(level ? { level } : {}),
    }),
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function listConversations() {
  const res = await fetch(`${API_BASE}/chat/conversations?user_id=${CURRENT_USER_ID}`);
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function getConversation(conversationId) {
  const res = await fetch(
    `${API_BASE}/chat/conversations/${conversationId}?user_id=${CURRENT_USER_ID}`
  );
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function getDocumentOutline(documentId) {
  const res = await fetch(
    `${API_BASE}/documents/${documentId}/outline?user_id=${CURRENT_USER_ID}`
  );
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function generateFlashcards(documentId, topicName, numCards = 10) {
  const res = await fetch(`${API_BASE}/flashcard/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      document_id: documentId,
      topic_name: topicName || null,
      num_cards: numCards,
    }),
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function saveFlashcardFromAnswer({
  front,
  back,
  sourceDocument,
  sourcePosition,
  topicName,
}) {
  const res = await fetch(`${API_BASE}/flashcard/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      front,
      back,
      source_document: sourceDocument ?? null,
      source_position: sourcePosition ?? null,
      topic_name: topicName ?? null,
    }),
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function listDueFlashcards(limit = 20) {
  const res = await fetch(
    `${API_BASE}/flashcard/due?user_id=${CURRENT_USER_ID}&limit=${limit}`
  );
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function reviewFlashcard(flashcardItemId, rating) {
  const res = await fetch(`${API_BASE}/flashcard/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      flashcard_item_id: flashcardItemId,
      rating,
    }),
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function getStudyPlan(days, courseName) {
  const params = new URLSearchParams({ user_id: CURRENT_USER_ID, days: String(days) });
  if (courseName) params.set("course_name", courseName);
  const res = await fetch(`${API_BASE}/study-plan?${params}`);
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function getProfile() {
  const res = await fetch(`${API_BASE}/profile?user_id=${CURRENT_USER_ID}`);
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function updateProfile({ preferredLevel, learningGoal }) {
  const res = await fetch(`${API_BASE}/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      preferred_level: preferredLevel ?? null,
      learning_goal: learningGoal ?? null,
    }),
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function listMemory(limit = 50) {
  const res = await fetch(`${API_BASE}/memory?user_id=${CURRENT_USER_ID}&limit=${limit}`);
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function deleteMemory(eventId) {
  const res = await fetch(`${API_BASE}/memory/${eventId}?user_id=${CURRENT_USER_ID}`, {
    method: "DELETE",
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

// Dựng URL mở tài liệu gốc. PDF nhảy đúng trang bằng fragment '#page=N' bóc từ
// position_ref dạng "Trang 5". DOCX dùng position_ref dạng "Mục n" — không có
// khái niệm trang nên KHÔNG gắn fragment, mở từ đầu file (hạn chế đã biết).
export function documentFileUrl(documentId, positionRef) {
  const base = `${API_BASE}/documents/${documentId}/file?user_id=${CURRENT_USER_ID}`;
  const match = /Trang\s+(\d+)/i.exec(positionRef || "");
  return match ? `${base}#page=${match[1]}` : base;
}
