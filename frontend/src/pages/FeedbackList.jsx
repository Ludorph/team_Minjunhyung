// S03 피드백 목록: 우선순위 정렬(서버), 기간·감정·상태 필터
import { useEffect, useState } from 'react'
import { api, LABELS } from '../api/client.js'
import { Score, SentimentBadge, StatusBadge, Tags } from '../components/Badges.jsx'
import { navigate } from '../router.js'

const EMPTY = { status: '', sentiment: '', topic: '', urgent: '', date_from: '', date_to: '' }

export default function FeedbackList({ initialFilters = {} }) {
  const [filters, setFilters] = useState({ ...EMPTY, ...initialFilters })
  const [items, setItems] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ''))
    api.listFeedbacks(params).then(setItems).catch((e) => setError(e.message))
  }, [filters])

  const set = (k) => (e) => setFilters({ ...filters, [k]: e.target.value })
  const filtered = Object.values(filters).some((v) => v !== '')

  return (
    <div>
      <div className="page-head">
        <h2>피드백<span className="count">{items.length}</span></h2>
        <div className="tools">
          <button onClick={() => navigate('/upload')}>일괄 업로드</button>
          <button className="primary" onClick={() => navigate('/feedbacks/new')}>직접 등록</button>
        </div>
      </div>

      <div className="filters">
        <select value={filters.status} onChange={set('status')}>
          <option value="">상태</option>
          {['PENDING', 'IN_PROGRESS', 'DONE'].map((s) => <option key={s} value={s}>{LABELS[s]}</option>)}
        </select>
        <select value={filters.sentiment} onChange={set('sentiment')}>
          <option value="">감정</option>
          {['NEGATIVE', 'NEUTRAL', 'POSITIVE'].map((s) => <option key={s} value={s}>{LABELS[s]}</option>)}
        </select>
        <select value={filters.topic} onChange={set('topic')}>
          <option value="">주제</option>
          {['품질', '배송', '가격', '서비스', '기타'].map((t) => <option key={t}>{t}</option>)}
        </select>
        <input type="date" value={filters.date_from} onChange={set('date_from')} aria-label="시작일" />
        <span className="muted">~</span>
        <input type="date" value={filters.date_to} onChange={set('date_to')} aria-label="종료일" />
        {filters.urgent && <span className="tag urgent">긴급만</span>}
        {filtered && <button className="ghost" onClick={() => setFilters(EMPTY)}>초기화</button>}
        <span className="spacer" />
        <small className="muted">우선순위 높은 순</small>
      </div>

      {error && <p className="error">{error}</p>}
      <div className="table-wrap">
        <table className="list">
          <thead>
            <tr><th className="num">우선순위</th><th>내용</th><th>감정</th><th>주제</th><th>고객</th><th>접수일시</th><th>상태</th></tr>
          </thead>
          <tbody>
            {items.map((f) => (
              <tr key={f.id} className="clickable" onClick={() => navigate(`/feedbacks/${f.id}`)}>
                <td className="num"><Score priority={f.priority} /></td>
                <td className="ellipsis"><Tags tags={f.tags} />{f.content}</td>
                <td><SentimentBadge sentiment={f.sentiment} /></td>
                <td className="muted">{f.topics.join(', ')}</td>
                <td>{f.customer_name || <span className="muted">익명</span>}</td>
                <td className="muted">{f.written_at.slice(5, 16).replace('T', ' ')}</td>
                <td><StatusBadge status={f.status} /></td>
              </tr>
            ))}
            {items.length === 0 && !error && (
              <tr><td colSpan={7} className="empty">조건에 맞는 피드백이 없습니다</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
