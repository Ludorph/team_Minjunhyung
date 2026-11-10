// S04 피드백 상세 / 답변 검토: 원문↔초안 대조, 점수 산출 근거, 전략 변경·수정·확정, 상태 변경
import { useCallback, useEffect, useState } from 'react'
import { api, LABELS } from '../api/client.js'
import { SentimentBadge, SourceBadge, StatusBadge, Tags } from '../components/Badges.jsx'
import { navigate } from '../router.js'

const ACTIONS = {
  PENDING: [['start', '처리 시작']],
  IN_PROGRESS: [['complete', '완료 처리']],
  DONE: [['reopen', '재오픈']],
}

export default function FeedbackDetail({ id }) {
  const [fb, setFb] = useState(null)
  const [text, setText] = useState('')
  const [strategy, setStrategy] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(() =>
    api.getFeedback(id).then((f) => {
      setFb(f)
      const last = f.drafts[f.drafts.length - 1]
      setText(last ? last.final_content || last.draft_content : '')
    }).catch((e) => setError(e.message)), [id])

  useEffect(() => { load() }, [load])

  const run = (fn, ok) => async () => {
    setError(''); setMsg('')
    try {
      await fn()
      setMsg(ok)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  if (!fb) return error ? <p className="error">{error}</p> : <p>불러오는 중...</p>
  const draft = fb.drafts[fb.drafts.length - 1]
  const p = fb.priority

  return (
    <div>
      <p><a href="#/feedbacks">← 목록으로</a></p>
      <h2>피드백 #{fb.id} <StatusBadge status={fb.status} /> <Tags tags={fb.tags} /></h2>
      {msg && <p className="ok">{msg}</p>}
      {error && <p className="error">{error}</p>}

      <div className="grid two">
        <section className="card">
          <h3>원문</h3>
          <p className="content">{fb.content}</p>
          <p className="muted">
            {fb.customer_name || '익명'} ({fb.grade || '-'}) · {LABELS[fb.source]} · {fb.written_at.replace('T', ' ').slice(0, 16)}
          </p>
          <p>감정: <SentimentBadge sentiment={fb.sentiment} />
            {fb.sentiment && <>
              <small className="muted"> 강도 {fb.sentiment.intensity} · 신뢰도 {fb.sentiment.confidence} </small>
              <SourceBadge ai={fb.sentiment.analyzer === 'LLM'} aiText="AI 분석 결과" fallbackText="규칙 기반 분석 (AI 대체)" />
            </>}
          </p>
          <p>주제: {fb.topics.join(', ') || '-'}</p>
          <h4>우선순위 산출 근거</h4>
          {p ? (
            <p className="formula">
              P = (부정강도 {p.neg_intensity} × 10) × 등급가중치 {p.grade_weight} × 시간가중치 {p.time_weight} = <b>{p.score}</b>
              {p.is_urgent ? ' → 긴급(≥15)' : ''}
            </p>
          ) : <p className="muted">분석 전</p>}
          <button onClick={run(() => api.reanalyze(id), '재분석 완료')}>재분석</button>
        </section>

        <section className="card">
          <h3>답변 초안 {draft && <small className="muted">({LABELS[draft.strategy]}{draft.confirmed ? ', 확정됨' : ''})</small>}</h3>
          {draft && (
            <p>
              <SourceBadge ai={draft.is_ai_generated} aiText="AI 생성 초안" fallbackText="템플릿 초안 (AI 대체)" />
              {draft.is_edited && <span className="tag edited">담당자 수정</span>}
              <small className="muted"> 담당자가 검토·확정해야 완료 처리할 수 있습니다.</small>
            </p>
          )}
          <div className="row">
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
              <option value="">자동 선택</option>
              <option value="APOLOGY">사과형</option>
              <option value="GUIDANCE">안내형</option>
              <option value="THANKS">감사형</option>
            </select>
            <button onClick={run(() => api.createDraft(id, strategy), '초안 생성됨')}>초안 생성</button>
          </div>
          <textarea rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder="초안을 생성하세요" />
          {draft && (
            <div className="row">
              <button onClick={run(() => api.editDraft(draft.id, text), '수정 저장됨')}>수정 저장</button>
              <button className="primary" onClick={run(() => api.confirmDraft(draft.id, text), '답변 확정됨')}>확정</button>
            </div>
          )}
        </section>
      </div>

      <section className="card">
        <h3>상태 변경</h3>
        <div className="row">
          {ACTIONS[fb.status].map(([action, label]) => (
            <button key={action} onClick={run(async () => {
              await api.changeStatus(id, action)
              if (action === 'complete') navigate('/feedbacks')
            }, `${label} 완료`)}>{label}</button>
          ))}
        </div>
        <ul className="history">
          {fb.histories.map((h, i) => (
            <li key={i}>{h.changed_at.replace('T', ' ').slice(0, 16)} · {LABELS[h.from_status]} → {LABELS[h.to_status]} (사용자 {h.changed_by})</li>
          ))}
        </ul>
      </section>
    </div>
  )
}
