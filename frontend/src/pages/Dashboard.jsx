// S02 대시보드: 감정·주제·상태 집계, 긴급 건수, 일별 추이
import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { BarList, TrendChart, TrendLegend } from '../components/Badges.jsx'
import { navigate } from '../router.js'

export default function Dashboard() {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.dashboard().then(setD).catch((e) => setError(e.message))
  }, [])

  // UC-05 E1: 통계 조회 실패 시 안내
  if (error) return <p className="error">데이터 조회 지연: {error}</p>
  if (!d) return <p className="loading">불러오는 중</p>

  return (
    <div>
      <div className="page-head">
        <h2>대시보드</h2>
      </div>

      <div className="stats">
        <div className="stat"><span>전체</span><b>{d.total}<small>건</small></b></div>
        <div className="stat clickable" onClick={() => navigate('/feedbacks?status=PENDING')}>
          <span>미처리</span><b>{d.by_status.PENDING}<small>건</small></b>
        </div>
        <div className="stat clickable" onClick={() => navigate('/feedbacks?status=IN_PROGRESS')}>
          <span>처리중</span><b>{d.by_status.IN_PROGRESS}<small>건</small></b>
        </div>
        <div className="stat urgent clickable" onClick={() => navigate('/feedbacks?urgent=true')}>
          <span>긴급 미완료</span><b>{d.urgent_count}<small>건</small></b>
        </div>
      </div>

      <section className="card">
        <div className="card-head">
          <h3>일별 감정 추이</h3>
          <TrendLegend />
        </div>
        <TrendChart rows={d.daily_trend} />
      </section>

      <div className="grid">
        <section className="card">
          <div className="card-head"><h3>감정</h3></div>
          <BarList data={d.by_sentiment} onClick={(k) => navigate(`/feedbacks?sentiment=${k}`)} />
        </section>
        <section className="card">
          <div className="card-head"><h3>주제</h3></div>
          <BarList data={d.by_topic} onClick={(k) => navigate(`/feedbacks?topic=${encodeURIComponent(k)}`)} />
        </section>
        <section className="card">
          <div className="card-head"><h3>처리 상태</h3></div>
          <BarList data={d.by_status} onClick={(k) => navigate(`/feedbacks?status=${k}`)} />
        </section>
      </div>
    </div>
  )
}
