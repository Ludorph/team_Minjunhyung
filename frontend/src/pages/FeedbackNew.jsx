// S05 피드백 단건 입력
import { useState } from 'react'
import { api } from '../api/client.js'
import { navigate } from '../router.js'

export default function FeedbackNew() {
  const [form, setForm] = useState({ customer_name: '', grade: 'REGULAR', source: 'REVIEW', content: '' })
  const [error, setError] = useState('')
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const body = { ...form, customer_name: form.customer_name || null, grade: form.customer_name ? form.grade : null }
      await api.createFeedback(body)
      navigate('/feedbacks')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className="page-head">
        <h2>피드백 직접 등록</h2>
        <button onClick={() => navigate('/upload')}>일괄 업로드</button>
      </div>
      <form className="card form" onSubmit={submit}>
        <div className="grid three">
          <label>고객명<input value={form.customer_name} onChange={set('customer_name')} placeholder="선택" /></label>
          <label>고객 등급
            <select value={form.grade} onChange={set('grade')} disabled={!form.customer_name}>
              <option value="VIP">VIP</option><option value="REGULAR">일반</option><option value="NEW">신규</option>
            </select>
          </label>
          <label>출처
            <select value={form.source} onChange={set('source')}>
              <option value="REVIEW">리뷰</option><option value="CONSULT">상담</option><option value="EMAIL">이메일</option>
            </select>
          </label>
        </div>
        <label>내용<textarea rows={7} value={form.content} onChange={set('content')} placeholder="리뷰, 상담 기록, 문의 메일 내용" required /></label>
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="button" onClick={() => navigate('/feedbacks')}>취소</button>
          <button className="primary" type="submit">등록</button>
        </div>
      </form>
    </div>
  )
}
