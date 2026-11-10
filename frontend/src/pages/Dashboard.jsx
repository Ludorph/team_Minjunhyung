// S02 대시보드: 감정·주제·상태 집계, 긴급 건수, 일별 추이
import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { BarList } from '../components/Badges.jsx'
import { navigate } from '../router.js'

export default function Dashboard() {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.dashboard().then(setD).catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!d) return <p>불러오는 중...</p>

  return (
    <div>
      <h2>대시보드</h2>
      <div className="stats">
        <div className="stat"><span>전체</span><b>{d.total}</b></div>
        <div className="stat clickable" onClick={() => navigate('/feedbacks?status=PENDING')}>
          <span>미처리</span><b>{d.by_status.PENDING}</b>
        </div>
        <div className="stat urgent clickable" onClick={() => navigate('/feedbacks?urgent=true')}>
          <span>긴급(미완료)</span><b>{d.urgent_count}</b>
        </div>
      </div>
      <div className="grid">
        <section className="card">
          <h3>감정별</h3>
          <BarList data={d.by_sentiment} onClick={(k) => navigate(`/feedbacks?sentiment=${k}`)} />
        </section>
        <section className="card">
          <h3>주제별</h3>
          <BarList data={d.by_topic} onClick={(k) => navigate(`/feedbacks?topic=${encodeURIComponent(k)}`)} />
        </section>
        <section className="card">
          <h3>상태별</h3>
          <BarList data={d.by_status} onClick={(k) => navigate(`/feedbacks?status=${k}`)} />
        </section>
      </div>
      <section className="card">
        <h3>일별 감정 추이</h3>
        <table>
          <thead><tr><th>날짜</th><th>긍정</th><th>중립</th><th>부정</th></tr></thead>
          <tbody>
            {d.daily_trend.map((r) => (
              <tr key={r.date}><td>{r.date}</td><td>{r.POSITIVE}</td><td>{r.NEUTRAL}</td><td>{r.NEGATIVE}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
