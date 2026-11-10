// 해시 기반 간단 라우팅 (S01~S07)
import { useEffect, useState } from 'react'
import Nav from './components/Nav.jsx'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import FeedbackList from './pages/FeedbackList.jsx'
import FeedbackDetail from './pages/FeedbackDetail.jsx'
import FeedbackNew from './pages/FeedbackNew.jsx'
import Upload from './pages/Upload.jsx'
import Accuracy from './pages/Accuracy.jsx'
import { navigate } from './router.js'

function useHashRoute() {
  const read = () => window.location.hash.replace(/^#/, '') || '/dashboard'
  const [route, setRoute] = useState(read)
  useEffect(() => {
    const onChange = () => setRoute(read())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

function loadUser() {
  try {
    return JSON.parse(localStorage.getItem('user'))
  } catch {
    return null
  }
}

export default function App() {
  const route = useHashRoute()
  const [user, setUser] = useState(loadUser)

  const onLogin = (token, u) => {
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(u))
    setUser(u)
    navigate('/dashboard')
  }
  const onLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
    navigate('/login')
  }

  if (!user || !localStorage.getItem('token') || route === '/login') {
    return <Login onLogin={onLogin} />
  }

  const [path, query = ''] = route.split('?')
  const params = Object.fromEntries(new URLSearchParams(query))
  let page
  let m
  if (path === '/dashboard') page = <Dashboard />
  else if (path === '/feedbacks') page = <FeedbackList initialFilters={params} />
  else if (path === '/feedbacks/new') page = <FeedbackNew />
  else if ((m = path.match(/^\/feedbacks\/(\d+)$/))) page = <FeedbackDetail id={Number(m[1])} />
  else if (path === '/upload') page = <Upload />
  else if (path === '/accuracy') page = user.role === 'ADMIN' ? <Accuracy /> : <p className="error">관리자 전용 화면입니다.</p>
  else page = <p>페이지를 찾을 수 없습니다.</p>

  return (
    <div className="app">
      <Nav user={user} route={path} onLogout={onLogout} />
      <main className="content">{page}</main>
    </div>
  )
}
