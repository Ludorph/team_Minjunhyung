const ITEMS = [
  ['/dashboard', '대시보드'],
  ['/feedbacks', '피드백 목록'],
  ['/feedbacks/new', '피드백 등록'],
  ['/upload', 'CSV 업로드'],
]

export default function Nav({ user, route, onLogout }) {
  const items = user.role === 'ADMIN' ? [...ITEMS, ['/accuracy', '정확도 검증']] : ITEMS
  return (
    <header className="nav">
      <strong className="brand">FeedbackCare</strong>
      <nav>
        {items.map(([path, label]) => (
          <a key={path} href={`#${path}`} className={route === path ? 'active' : ''}>
            {label}
          </a>
        ))}
      </nav>
      <span className="who">
        {user.name} ({user.role}) <button onClick={onLogout}>로그아웃</button>
      </span>
    </header>
  )
}
