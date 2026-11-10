// S07 분석 정확도 검증 (관리자 전용): 정답 라벨 표본 vs AI 결과 일치율
import { useEffect, useState } from 'react'
import { api, LABELS } from '../api/client.js'

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
      await load()
    } catch (err) {
      setError(err.message)
    }
  }
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const pct = (v) => (v == null ? '-' : `${(v * 100).toFixed(1)}%`)

  return (
    <div>
      <h2>분석 정확도 검증</h2>
      <form className="row card" onSubmit={submit}>
        <b>정답 라벨 입력</b>
        <input placeholder="피드백 ID" value={form.id} onChange={set('id')} required style={{ width: 100 }} />
        <select value={form.label} onChange={set('label')}>
          {['POSITIVE', 'NEUTRAL', 'NEGATIVE'].map((s) => <option key={s} value={s}>{LABELS[s]}</option>)}
        </select>
        <select value={form.topic} onChange={set('topic')}>
          {['품질', '배송', '가격', '서비스', '기타'].map((t) => <option key={t}>{t}</option>)}
        </select>
        <button className="primary">저장</button>
      </form>
      {error && <p className="error">{error}</p>}
      {rep && (
        <>
          <div className="stats">
            <div className="stat"><span>표본 수</span><b>{rep.sample_size}</b></div>
            <div className="stat"><span>감정 일치율</span><b>{pct(rep.sentiment_accuracy)}</b></div>
            <div className="stat"><span>주제 일치율</span><b>{pct(rep.topic_accuracy)}</b></div>
          </div>
          <table className="list">
            <thead><tr><th>ID</th><th>내용</th><th>정답 감정</th><th>AI 감정</th><th>정답 주제</th><th>AI 주제</th></tr></thead>
            <tbody>
              {rep.items.map((r) => (
                <tr key={r.feedback_id}>
                  <td>{r.feedback_id}</td>
                  <td className="ellipsis">{r.content}</td>
                  <td>{LABELS[r.gold_label]}</td>
                  <td className={r.label_match ? 'ok' : 'error'}>{LABELS[r.predicted_label] || '-'}</td>
                  <td>{r.gold_topic}</td>
                  <td className={r.topic_match ? 'ok' : 'error'}>{r.predicted_topics.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
