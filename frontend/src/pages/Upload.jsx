// S06 CSV 일괄 업로드: 결과(성공/오류 행) 표시, 형식 오류 시 재업로드
import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { navigate } from '../router.js'

const POLL_MS = 700

export default function Upload() {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [batch, setBatch] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // 백그라운드 분석이 저장된 행 수만큼 끝날 때까지 배치 상태를 다시 조회한다
  useEffect(() => {
    if (!result || (batch && batch.analyzed_rows >= result.saved_rows)) return
    const timer = setTimeout(async () => {
      try { setBatch(await api.batchStatus(result.batch_id)) } catch (err) { setError(err.message) }
    }, POLL_MS)
    return () => clearTimeout(timer)
  }, [result, batch])

  const submit = async (e) => {
    e.preventDefault()
    if (!file) return
    setError(''); setResult(null); setBatch(null); setBusy(true)
    try {
      const r = await api.uploadCsv(file)
      setResult(r)
      setBatch(await api.batchStatus(r.batch_id))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card form">
      <h2>CSV 일괄 업로드</h2>
      <p className="muted">필수 컬럼: customer_name, grade, source, written_at, content</p>
      <form onSubmit={submit} className="row">
        <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0])} />
        <button className="primary" disabled={!file || busy}>{busy ? '업로드 중...' : '업로드'}</button>
      </form>
      {error && <p className="error">형식 오류: {error} — 파일을 확인 후 다시 업로드하세요.</p>}
      {result && (
        <div>
          <p className="ok">{result.message}</p>
          <p>배치 #{result.batch_id} · 전체 {result.total_rows}행 · 성공 {result.saved_rows}행 · 오류 {result.error_rows}행
            {batch && <> · 분석 완료 {batch.analyzed_rows}/{result.saved_rows}행
              {batch.analyzed_rows < result.saved_rows && ' (진행 중...)'}</>}
          </p>
          {result.errors.length > 0 && (
            <table>
              <thead><tr><th>행</th><th>오류 사유</th></tr></thead>
              <tbody>{result.errors.map((e) => <tr key={e.row}><td>{e.row}</td><td>{e.reason}</td></tr>)}</tbody>
            </table>
          )}
          <button onClick={() => navigate('/feedbacks')}>목록으로 이동</button>
        </div>
      )}
    </div>
  )
}
