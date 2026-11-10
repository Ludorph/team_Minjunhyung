// S03 피드백 목록: 우선순위 정렬(서버), 기간·감정·상태 필터
import { useEffect, useState } from 'react'
import { api, LABELS } from '../api/client.js'
import { SentimentBadge, StatusBadge, Tags } from '../components/Badges.jsx'
import { navigate } from '../router.js'

export default function FeedbackList({ initialFilters = {} }) {
  const [filters, setFilters] = useState({
    status: '', sentiment: '', topic: '', urgent: '', date_from: '', date_to: '', ...initialFilters,
  })
  const [items, setItems] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ''))
    api.listFeedbacks(params).then(setItems).catch((e) => setError(e.message))
  }, [filters])

  const set = (k) => (e) => setFilters({ ...filters, [k]: e.target.value })

  return (
    <div>
      <h2>피드백 목록 <small className="muted">({items.length}건, 우선순위 순)</small></h2>
      <div className="filters">
        <select value={filters.status} onChange={set('status')}>
          <option value="">상태 전체</option>
          {['PENDING', 'IN_PROGRESS', 'DONE'].map((s) => <option key={s} value={s}>{LABELS[s]}</option>)}
        </select>
        <select value={filters.sentiment} onChange={set('sentiment')}>
          <option value="">감정 전체</option>
          {['NEGATIVE', 'NEUTRAL', 'POSITIVE'].map((s) => <option key={s} value={s}>{LABELS[s]}</option>)}
        </select>
        <select value={filters.topic} onChange={set('topic')}>
          <option value="">주제 전체</option>
          {['품질', '배송', '가격', '서비스', '기타'].map((t) => <option key={t}>{t}</option>)}
        </select>
        <label>시작 <input type="date" value={filters.date_from} onChange={set('date_from')} /></label>
        <label>종료 <input type="date" value={filters.date_to} onChange={set('date_to')} /></label>
        {filters.urgent && <button onClick={() => setFilters({ ...filters, urgent: '' })}>긴급 필터 해제</button>}
      </div>
      {error && <p className="error">{error}</p>}
      <table className="list">
        <thead>
          <tr><th>점수</th><th>태그</th><th>감정</th><th>주제</th><th>내용</th><th>고객</th><th>작성일</th><th>상태</th></tr>
        </thead>
        <tbody>
          {items.map((f) => (
            <tr key={f.id} className="clickable" onClick={() => navigate(`/feedbacks/${f.id}`)}>
              <td className="num">{f.priority ? f.priority.score.toFixed(1) : '-'}</td>
              <td><Tags tags={f.tags} /></td>
              <td><SentimentBadge sentiment={f.sentiment} /></td>
              <td>{f.topics.join(', ')}</td>
              <td className="ellipsis">{f.content}</td>
              <td>{f.customer_name || '-'} {f.grade && <small className="muted">{f.grade}</small>}</td>
              <td>{f.written_at.slice(0, 16).replace('T', ' ')}</td>
              <td><StatusBadge status={f.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
