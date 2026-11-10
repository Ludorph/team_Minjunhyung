import { LABELS } from '../api/client.js'

export function SentimentBadge({ sentiment }) {
  if (!sentiment) return <span className="badge muted">분석 대기</span>
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

// 운영계획서 13절: AI 생성 결과임을 표시하고, 규칙 기반 대체 여부를 구분한다
export function SourceBadge({ ai, aiText, fallbackText }) {
  return <span className={`tag ${ai ? 'ai' : 'rule'}`}>{ai ? aiText : fallbackText}</span>
}

// 차트 라이브러리 없이 CSS 막대로 표시
export function BarList({ data, onClick }) {
  const max = Math.max(1, ...Object.values(data))
  return (
    <ul className="bars">
      {Object.entries(data).map(([k, v]) => (
        <li key={k} onClick={onClick ? () => onClick(k) : undefined} className={onClick ? 'clickable' : ''}>
          <span className="bar-label">{LABELS[k] || k}</span>
          <span className="bar" style={{ width: `${(v / max) * 100}%` }} />
          <span className="bar-value">{v}</span>
        </li>
      ))}
    </ul>
  )
}
