// S01 로그인
import { useState } from 'react'
import { api } from '../api/client.js'

export default function Login({ onLogin }) {
  const [loginId, setLoginId] = useState('agent1')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const res = await api.login(loginId, password)
      onLogin(res.token, res.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      <form className="card login" onSubmit={submit}>
        <span className="brand">Feedback<em>Care</em></span>
        <label>아이디<input value={loginId} onChange={(e) => setLoginId(e.target.value)} autoFocus /></label>
        <label>비밀번호<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p className="error">{error}</p>}
        <button type="submit" className="primary" disabled={busy}>{busy ? '로그인 중' : '로그인'}</button>
      </form>
      <p className="copyright">© 2026 TeamMinJunhyung</p>
    </div>
  )
}
