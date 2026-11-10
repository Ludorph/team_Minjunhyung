import { LABELS } from '../api/client.js'

export function SentimentBadge({ sentiment }) {
  if (!sentiment) return <span className="badge">분석 대기</span>
  return <span className={`badge s-${sentiment.label}`}>{LABELS[sentiment.label]}</span>
}

export function StatusBadge({ status }) {
  return <span className={`badge st-${status}`}>{LABELS[status]}</span>
}

export function Tags({ tags }) {
  return (
    <>
      {tags.map((t) => (
        <span key={t} className={`tag ${t === '긴급' ? 'urgent' : 'vip'}`}>{t}</span>
      ))}
    </>
  )
}

// 긴급 임계치(15)와 그 절반을 기준으로 점수 색을 나눈다
export function Score({ priority }) {
  if (!priority) return <span className="score">-</span>
  const level = priority.is_urgent ? 'high' : priority.score >= 7.5 ? 'mid' : ''
  return <span className={`score ${level}`}>{priority.score.toFixed(1)}</span>
}

// 운영계획서 13절: AI 생성 결과임을 표시하고, 규칙 기반 대체 여부를 구분한다
export function SourceBadge({ ai, aiText, fallbackText }) {
  return <span className={`tag ${ai ? 'ai' : 'rule'}`}>{ai ? aiText : fallbackText}</span>
}

// 차트 라이브러리 없이 CSS 막대로 표시. 감정·상태 키는 고유 색을 쓴다
export function BarList({ data, onClick }) {
  const max = Math.max(1, ...Object.values(data))
  return (
    <ul className="bars">
      {Object.entries(data).map(([k, v]) => (
        <li key={k} onClick={onClick ? () => onClick(k) : undefined} className={onClick ? 'clickable' : ''}>
          <span className="bar-label">{LABELS[k] || k}</span>
          <span className="bar-track">
            <span className={`bar c-${k}`} style={{ width: `${(v / max) * 100}%` }} />
          </span>
          <span className="bar-value">{v}</span>
        </li>
      ))}
    </ul>
  )
}

const TREND_KEYS = ['POSITIVE', 'NEUTRAL', 'NEGATIVE']

// 일별 감정 추이: 날짜마다 긍정·중립·부정을 쌓은 막대
export function TrendChart({ rows }) {
  if (rows.length === 0) return <p className="empty">추이를 표시할 데이터가 없습니다.</p>
  const totals = rows.map((r) => TREND_KEYS.reduce((n, k) => n + r[k], 0))
  const max = Math.max(1, ...totals)
  return (
    <div>
      <div className="trend">
        {rows.map((r, i) => (
          <div key={r.date} className="trend-col" title={`${r.date} · 긍정 ${r.POSITIVE} / 중립 ${r.NEUTRAL} / 부정 ${r.NEGATIVE}`}>
            <span className="trend-total">{totals[i]}</span>
            <div className="trend-stack" style={{ height: `${(totals[i] / max) * 85}%` }}>
              {TREND_KEYS.map((k) => (
                <span key={k} className={k} style={{ height: `${totals[i] ? (r[k] / totals[i]) * 100 : 0}%` }} />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="trend-dates">
        {rows.map((r) => <span key={r.date}>{r.date.slice(5)}</span>)}
      </div>
    </div>
  )
}

export function TrendLegend() {
  return (
    <div className="legend">
      <span><i className="trend-stack-key POSITIVE" />긍정</span>
      <span><i className="trend-stack-key NEUTRAL" />중립</span>
      <span><i className="trend-stack-key NEGATIVE" />부정</span>
    </div>
  )
}
