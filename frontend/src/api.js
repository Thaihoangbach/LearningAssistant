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


export async function uploadDocument(file, courseName, displayName) {
  const form = new FormData();
  form.append("file", file);
  const params = new URLSearchParams({ user_id: CURRENT_USER_ID });
  if (courseName) params.set("course_name", courseName);
  if (displayName) params.set("display_name", displayName);
  const url = `${API_BASE}/documents?${params}`;
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

export async function generateQuiz(documentId, topicName, numQuestions = 5, difficulty, generationMode) {
  const res = await fetch(`${API_BASE}/quiz/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      document_id: documentId,
      topic_name: topicName || null,
      num_questions: numQuestions,
      // Không gửi difficulty khi người dùng để "Tự động" — backend sẽ dùng
      // trình độ đã lưu hoặc suy từ mastery (app/services/learner_context.py).
      ...(difficulty ? { difficulty } : {}),
      // Không gửi generation_mode khi để "Tự động" — cùng lý do difficulty ở
      // trên (Learning Loop Phase 3).
      ...(generationMode ? { generation_mode: generationMode } : {}),
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
      // preference đã lưu hoặc suy từ mastery (app/services/learner_context.py).
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

export async function generateFlashcards(documentId, topicName, numCards = 10, generationMode) {
  const res = await fetch(`${API_BASE}/flashcard/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      document_id: documentId,
      topic_name: topicName || null,
      num_cards: numCards,
      // Không gửi generation_mode khi để "Tự động" (Learning Loop Phase 3).
      ...(generationMode ? { generation_mode: generationMode } : {}),
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

export async function getFlashcardBoard() {
  const res = await fetch(`${API_BASE}/flashcard/board?user_id=${CURRENT_USER_ID}`);
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function getFlashcardMistakes(limit = 20) {
  const res = await fetch(
    `${API_BASE}/flashcard/mistakes?user_id=${CURRENT_USER_ID}&limit=${limit}`
  );
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function getFlashcardHistory(itemId) {
  const res = await fetch(
    `${API_BASE}/flashcard/${itemId}/history?user_id=${CURRENT_USER_ID}`
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

export async function listCourses() {
  const res = await fetch(`${API_BASE}/courses?user_id=${CURRENT_USER_ID}`);
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function setCourseExamDate(courseName, examDateIso) {
  const res = await fetch(
    `${API_BASE}/courses/${encodeURIComponent(courseName)}/exam-date`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: CURRENT_USER_ID, exam_date: examDateIso }),
    }
  );
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function deleteCourseExamDate(courseName) {
  const res = await fetch(
    `${API_BASE}/courses/${encodeURIComponent(courseName)}/exam-date?user_id=${CURRENT_USER_ID}`,
    { method: "DELETE" }
  );
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

// courseNames: string[] — mỗi tên môn thành một cặp course_names= riêng, khớp
// FastAPI `course_names: list[str] = Query(...)` ở backend
// (app/routers/study_plan.py). Môn chưa đặt ngày thi làm backend trả 400 với
// thông báo liệt kê rõ tên môn còn thiếu — để nguyên lỗi đó nổi lên UI qua
// raiseFriendlyError, không đoán/ẩn.
export async function getStudyPlan(courseNames) {
  const params = new URLSearchParams({ user_id: CURRENT_USER_ID });
  for (const name of courseNames) params.append("course_names", name);
  const res = await fetch(`${API_BASE}/study-plan?${params}`);
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function markTopicReviewed(topicName, courseName) {
  const res = await fetch(`${API_BASE}/study-plan/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      topic_name: topicName,
      course_name: courseName ?? null,
    }),
  });
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

export async function resetProfile() {
  const res = await fetch(`${API_BASE}/profile?user_id=${CURRENT_USER_ID}`, {
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
