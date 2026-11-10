// S01 로그인
import { useState } from 'react'
import { api } from '../api/client.js'

export default function Login({ onLogin }) {
  const [loginId, setLoginId] = useState('agent1')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const res = await api.login(loginId, password)
      onLogin(res.token, res.user)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form className="card login" onSubmit={submit}>
      <h1>FeedbackCare</h1>
      <p className="muted">중소기업용 고객 피드백 감정 분석 및 대응 지원 시스템</p>
      <label>아이디<input value={loginId} onChange={(e) => setLoginId(e.target.value)} /></label>
      <label>비밀번호<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
      {error && <p className="error">{error}</p>}
      <button type="submit">로그인</button>
    </form>
  )
}
