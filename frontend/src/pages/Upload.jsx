// S06 CSV 일괄 업로드: 결과(성공/오류 행) 표시, 형식 오류 시 재업로드
import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { navigate } from '../router.js'

const POLL_MS = 700

export default function Upload() {
  const [file, setFile] = useState(null)
  const [over, setOver] = useState(false)
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

  const onDrop = (e) => {
    e.preventDefault()
    setOver(false)
    if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0])
  }

  const analyzed = batch ? batch.analyzed_rows : 0
  const pct = result && result.saved_rows ? Math.round((analyzed / result.saved_rows) * 100) : 0

  return (
    <div>
      <div className="page-head">
        <h2>일괄 업로드</h2>
      </div>

      <form className="card form" onSubmit={submit}>
        <label
          className={`dropzone ${over ? 'over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true) }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
        >
          <span>
            {file
              ? <>{file.name} <span className="muted">· {(file.size / 1024).toFixed(1)} KB</span></>
              : <span className="muted">CSV 파일을 선택하거나 여기로 끌어 오세요</span>}
          </span>
          <span className="pick">파일 선택</span>
          <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0])} />
        </label>
        <small className="muted">
          UTF-8 CSV, 첫 줄 컬럼: <code>customer_name</code> <code>grade</code> <code>source</code> <code>written_at</code> <code>content</code>
        </small>
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button className="primary" disabled={!file || busy}>{busy ? '업로드 중' : '업로드'}</button>
        </div>
      </form>

      {result && (
        <section className="card">
          <div className="card-head">
            <h3>업로드 결과 <span className="muted">#{result.batch_id}</span></h3>
            <button onClick={() => navigate('/feedbacks')}>피드백 목록</button>
          </div>
          <div className="summary">
            <div><span>전체</span><b>{result.total_rows}</b></div>
            <div><span>등록</span><b>{result.saved_rows}</b></div>
            <div className={result.error_rows ? 'bad' : ''}><span>오류</span><b>{result.error_rows}</b></div>
          </div>
          <small className="muted">
            분석 {analyzed} / {result.saved_rows}건 {analyzed < result.saved_rows ? '진행 중' : '완료'}
          </small>
          <div className="progress"><span style={{ width: `${pct}%` }} /></div>
          {result.errors.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead><tr><th>행 번호</th><th>사유</th></tr></thead>
                <tbody>{result.errors.map((e) => <tr key={e.row}><td>{e.row}</td><td>{e.reason}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
