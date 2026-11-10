// REST API 클라이언트 (axios). 토큰은 localStorage 에 보관한다.
import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !err.config.url.includes('/auth/login')) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.hash = '#/login'
    }
    const detail = err.response?.data?.detail
    err.message = typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : err.message
    return Promise.reject(err)
  },
)

const data = (p) => p.then((r) => r.data)

export const api = {
  login: (login_id, password) => data(http.post('/auth/login', { login_id, password })),
  me: () => data(http.get('/auth/me')),

  listFeedbacks: (params) => data(http.get('/feedbacks', { params })),
  getFeedback: (id) => data(http.get(`/feedbacks/${id}`)),
  createFeedback: (body) => data(http.post('/feedbacks', body)),
  uploadCsv: (file) => {
    const form = new FormData()
    form.append('file', file)
    return data(http.post('/feedbacks/upload', form))
  },
  batchStatus: (id) => data(http.get(`/feedbacks/batches/${id}`)),
  changeStatus: (id, action) => data(http.patch(`/feedbacks/${id}/status`, { action })),
  reanalyze: (id) => data(http.post(`/feedbacks/${id}/analyze`)),
  setGoldLabel: (id, label, topic) => data(http.put(`/feedbacks/${id}/gold-label`, { label, topic })),

  createDraft: (feedbackId, strategy) => data(http.post(`/feedbacks/${feedbackId}/drafts`, { strategy: strategy || null })),
  editDraft: (draftId, text) => data(http.patch(`/drafts/${draftId}`, { text })),
  confirmDraft: (draftId, final_content) => data(http.patch(`/drafts/${draftId}/confirm`, { final_content })),

  dashboard: () => data(http.get('/dashboard/summary')),
  accuracy: () => data(http.get('/dashboard/accuracy')),
}

export const LABELS = {
  POSITIVE: '긍정', NEUTRAL: '중립', NEGATIVE: '부정',
  PENDING: '미처리', IN_PROGRESS: '처리중', DONE: '완료',
  APOLOGY: '사과형', GUIDANCE: '안내형', THANKS: '감사형',
  REVIEW: '리뷰', CONSULT: '상담', EMAIL: '이메일',
}
