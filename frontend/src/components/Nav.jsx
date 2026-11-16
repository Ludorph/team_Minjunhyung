const ITEMS = [
  ['/dashboard', '대시보드'],
  ['/feedbacks', '피드백'],
  ['/feedbacks/new', '직접 등록'],
  ['/upload', '일괄 업로드'],
]

const ROLE_LABELS = { ADMIN: '관리자', AGENT: '상담원' }

export default function Nav({ user, route, onLogout }) {
  const items = user.role === 'ADMIN' ? [...ITEMS, ['/accuracy', '분석 정확도']] : ITEMS
  return (
    <header className="nav">
      <a className="brand" href="#/dashboard">Feedback<em>Care</em></a>
      <nav>
        {items.map(([path, label]) => (
          <a key={path} href={`#${path}`} className={route === path ? 'active' : ''}>
            {label}
          </a>
        ))}
      </nav>
      <span className="who">
        <span className="name"><b>{user.name}</b> {ROLE_LABELS[user.role] || user.role}</span>
        <span className="sep" />
        <button onClick={onLogout}>로그아웃</button>
      </span>
    </header>
  )
}
