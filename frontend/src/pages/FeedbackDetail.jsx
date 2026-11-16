// S04 피드백 상세 / 답변 검토: 원문↔초안 대조, 점수 산출 근거, 전략 변경·수정·확정, 상태 변경
import { useCallback, useEffect, useState } from 'react'
import { api, LABELS } from '../api/client.js'
import { SentimentBadge, SourceBadge, StatusBadge, Tags } from '../components/Badges.jsx'
import { navigate } from '../router.js'

const ACTIONS = {
  PENDING: [['start', '처리 시작']],
  IN_PROGRESS: [['complete', '처리 완료']],
  DONE: [['reopen', '다시 열기']],
}

const GRADES = { VIP: 'VIP', REGULAR: '일반', NEW: '신규' }

const time = (s) => s.replace('T', ' ').slice(0, 16)

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

  if (!fb) return error ? <p className="error">{error}</p> : <p className="loading">불러오는 중</p>
  const draft = fb.drafts[fb.drafts.length - 1]
  const p = fb.priority

  return (
    <div>
      <a className="back" href="#/feedbacks">피드백 목록</a>
      <div className="page-head">
        <div className="title-row">
          <h2>#{fb.id}</h2>
          <StatusBadge status={fb.status} />
          <Tags tags={fb.tags} />
        </div>
        <div className="tools">
          {ACTIONS[fb.status].map(([action, label]) => (
            <button key={action} className="primary" onClick={run(async () => {
              await api.changeStatus(id, action)
              if (action === 'complete') navigate('/feedbacks')
            }, `${label}했습니다`)}>{label}</button>
          ))}
        </div>
      </div>
      {msg && <p className="ok">{msg}</p>}
      {error && <p className="error">{error}</p>}

      <div className="grid two">
        <section className="card">
          <div className="card-head">
            <h3>고객 의견</h3>
            <button className="ghost" onClick={run(() => api.reanalyze(id), '다시 분석했습니다')}>다시 분석</button>
          </div>
          <p className="quote">{fb.content}</p>
          <dl className="meta">
            <dt>고객</dt>
            <dd>{fb.customer_name || '익명'}{fb.grade && <span className="muted">· {GRADES[fb.grade] || fb.grade}</span>}</dd>
            <dt>접수</dt>
            <dd>{LABELS[fb.source]} <span className="muted">· {time(fb.written_at)}</span></dd>
            <dt>감정</dt>
            <dd>
              <SentimentBadge sentiment={fb.sentiment} />
              {fb.sentiment && <>
                <span className="muted">강도 {fb.sentiment.intensity}</span>
                <SourceBadge ai={fb.sentiment.analyzer === 'LLM'} aiText="AI 분석" fallbackText="규칙 기반 분석" />
              </>}
            </dd>
            <dt>주제</dt>
            <dd>{fb.topics.join(', ') || '-'}</dd>
          </dl>
          <h4>우선순위</h4>
          {p ? (
            <p className="formula">
              부정 강도 {p.neg_intensity} × 10 × 등급 {p.grade_weight} × 경과 시간 {p.time_weight} = <b>{p.score}점</b>
              {p.is_urgent && <span className="urgent-note"> · 긴급</span>}
            </p>
          ) : <p className="muted">분석 전</p>}
        </section>

        <section className="card">
          <div className="card-head">
            <h3>답변</h3>
            {draft && (
              <span>
                <SourceBadge ai={draft.is_ai_generated} aiText="AI 작성" fallbackText="템플릿" />
                {draft.is_edited && <span className="tag edited">수정됨</span>}
                {draft.confirmed && <span className="badge st-DONE">확정</span>}
              </span>
            )}
          </div>
          <div className="row">
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)} aria-label="답변 유형">
              <option value="">유형 자동</option>
              <option value="APOLOGY">사과</option>
              <option value="GUIDANCE">안내</option>
              <option value="THANKS">감사</option>
            </select>
            <button onClick={run(() => api.createDraft(id, strategy), '초안을 만들었습니다')}>
              {draft ? '다시 작성' : '초안 작성'}
            </button>
          </div>
          <textarea rows={10} value={text} onChange={(e) => setText(e.target.value)} placeholder="초안 작성을 누르면 답변 초안이 들어갑니다" style={{ marginTop: 8 }} />
          <p className="notice">AI가 작성한 초안은 내용을 확인한 뒤 확정해 주세요. 확정한 답변이 있어야 처리 완료할 수 있습니다.</p>
          {draft && (
            <div className="actions">
              <button onClick={run(() => api.editDraft(draft.id, text), '저장했습니다')}>저장</button>
              <button className="primary" onClick={run(() => api.confirmDraft(draft.id, text), '답변을 확정했습니다')}>확정</button>
            </div>
          )}
        </section>
      </div>

      <section className="card">
        <div className="card-head"><h3>처리 이력</h3></div>
        {fb.histories.length === 0 ? <p className="muted">아직 이력이 없습니다</p> : (
          <ul className="timeline">
            {fb.histories.map((h, i) => (
              <li key={i}>
                <time>{time(h.changed_at)}</time>
                <span>{LABELS[h.from_status]} → {LABELS[h.to_status]}</span>
                <span className="muted">사용자 {h.changed_by}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
