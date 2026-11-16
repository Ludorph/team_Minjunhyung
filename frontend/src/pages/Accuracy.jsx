// S07 분석 정확도 검증 (관리자 전용): 정답 라벨 표본 vs AI 결과 일치율
import { useEffect, useState } from 'react'
import { api, LABELS } from '../api/client.js'

// NFR-01 목표: 표본 30건 이상, 감정 80%, 주제 70%
const MIN_SAMPLE = 30
const GOALS = { sentiment: 0.8, topic: 0.7 }

function Goal({ value, goal }) {
  const v = value ?? 0
  return (
    <div className="goal" title={`목표 ${goal * 100}%`}>
      <span className={v >= goal ? 'met' : ''} style={{ width: `${v * 100}%` }} />
      <i style={{ left: `${goal * 100}%` }} />
    </div>
  )
}

export default function Accuracy() {
  const [rep, setRep] = useState(null)
  const [form, setForm] = useState({ id: '', label: 'NEGATIVE', topic: '품질' })
  const [error, setError] = useState('')

  const load = () => api.accuracy().then(setRep).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.setGoldLabel(Number(form.id), form.label, form.topic)
      setForm({ ...form, id: '' })
      await load()
    } catch (err) {
      setError(err.message)
    }
  }
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const pct = (v) => (v === null || v === undefined ? '-' : `${(v * 100).toFixed(1)}%`)

  return (
    <div>
      <div className="page-head">
        <h2>분석 정확도</h2>
      </div>

      {rep && (
        <div className="stats">
          <div className="stat">
            <span>정답 표본</span><b>{rep.sample_size}<small>/ {MIN_SAMPLE}건</small></b>
            <Goal value={Math.min(rep.sample_size / MIN_SAMPLE, 1)} goal={1} />
          </div>
          <div className="stat">
            <span>감정 일치율 <small className="muted">목표 80%</small></span><b>{pct(rep.sentiment_accuracy)}</b>
            <Goal value={rep.sentiment_accuracy} goal={GOALS.sentiment} />
          </div>
          <div className="stat">
            <span>주제 일치율 <small className="muted">목표 70%</small></span><b>{pct(rep.topic_accuracy)}</b>
            <Goal value={rep.topic_accuracy} goal={GOALS.topic} />
          </div>
        </div>
      )}

      <form className="filters" onSubmit={submit}>
        <input placeholder="피드백 번호" value={form.id} onChange={set('id')} required style={{ width: 120 }} />
        <select value={form.label} onChange={set('label')} aria-label="정답 감정">
          {['POSITIVE', 'NEUTRAL', 'NEGATIVE'].map((s) => <option key={s} value={s}>{LABELS[s]}</option>)}
        </select>
        <select value={form.topic} onChange={set('topic')} aria-label="정답 주제">
          {['품질', '배송', '가격', '서비스', '기타'].map((t) => <option key={t}>{t}</option>)}
        </select>
        <button className="primary">정답 추가</button>
      </form>
      {error && <p className="error">{error}</p>}
      {rep && (
        <>
          <div className="table-wrap">
            <table className="list">
              <thead><tr><th>번호</th><th>내용</th><th>정답 감정</th><th>분석 감정</th><th>정답 주제</th><th>분석 주제</th></tr></thead>
              <tbody>
                {rep.items.map((r) => (
                  <tr key={r.feedback_id}>
                    <td className="muted">{r.feedback_id}</td>
                    <td className="ellipsis">{r.content}</td>
                    <td>{LABELS[r.gold_label]}</td>
                    <td>{LABELS[r.predicted_label] || '-'} {!r.label_match && <span className="tag urgent">불일치</span>}</td>
                    <td>{r.gold_topic}</td>
                    <td>{r.predicted_topics.join(', ')} {!r.topic_match && <span className="tag urgent">불일치</span>}</td>
                  </tr>
                ))}
                {rep.items.length === 0 && <tr><td colSpan={6} className="empty">등록한 정답이 없습니다</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
