const API_BASE = "http://localhost:8001";

// user_id tạm thời cố định cho walking skeleton — F5 (đăng nhập thật) chưa làm ở bước này.
export const CURRENT_USER_ID = "demo-user";

export async function uploadDocument(file, courseName) {
  const form = new FormData();
  form.append("file", file);
  const url = `${API_BASE}/documents?user_id=${CURRENT_USER_ID}&course_name=${encodeURIComponent(courseName || "")}`;
  const res = await fetch(url, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listDocuments() {
  const res = await fetch(`${API_BASE}/documents?user_id=${CURRENT_USER_ID}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteDocument(documentId) {
  const res = await fetch(`${API_BASE}/documents/${documentId}?user_id=${CURRENT_USER_ID}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function generateQuiz(documentId, topicName, numQuestions = 5) {
  const res = await fetch(`${API_BASE}/quiz/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      document_id: documentId,
      topic_name: topicName || null,
      num_questions: numQuestions,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
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
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMastery() {
  const res = await fetch(`${API_BASE}/mastery?user_id=${CURRENT_USER_ID}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function askQuestion(question, conversationId) {
  const res = await fetch(`${API_BASE}/chat/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      question,
      conversation_id: conversationId || null,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listConversations() {
  const res = await fetch(`${API_BASE}/chat/conversations?user_id=${CURRENT_USER_ID}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getConversation(conversationId) {
  const res = await fetch(
    `${API_BASE}/chat/conversations/${conversationId}?user_id=${CURRENT_USER_ID}`
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
