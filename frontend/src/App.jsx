import { useCallback, useEffect, useRef, useState } from 'react'
import { createPayment, getPayments, getWallet } from './api'

const STATUS_LABELS = {
  new: 'Новый',
  processing: 'Обработка',
  succeeded: 'Успешно',
  failed: 'Ошибка',
}

const STATUS_COLORS = {
  new: '#666',
  processing: '#e68a00',
  succeeded: '#1a8a3f',
  failed: '#d93025',
}

export default function App() {
  const [balance, setBalance] = useState(null)
  const [payments, setPayments] = useState([])
  const [amount, setAmount] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const pollingRef = useRef(null)

  const refresh = useCallback(async () => {
    const [w, p] = await Promise.all([getWallet(), getPayments()])
    setBalance(w.balance)
    setPayments(p)
    return p
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    const hasPending = payments.some(
      (p) => p.status === 'new' || p.status === 'processing',
    )

    if (hasPending && !pollingRef.current) {
      pollingRef.current = setInterval(refresh, 3000)
    } else if (!hasPending && pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }
  }, [payments, refresh])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await createPayment(amount)
      setAmount('')
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <h1>Кошелёк</h1>

      <div style={{ fontSize: '2rem', margin: '16px 0' }}>
        {balance !== null ? `${balance} ₽` : '...'}
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
        <input
          type="text"
          inputMode="decimal"
          placeholder="Сумма, ₽"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          disabled={loading}
          style={{ padding: '8px 12px', fontSize: '1rem', flex: 1 }}
        />
        <button
          type="submit"
          disabled={loading || !amount}
          style={{ padding: '8px 20px', fontSize: '1rem', cursor: 'pointer' }}
        >
          {loading ? '...' : 'Пополнить'}
        </button>
      </form>

      {error && <div style={{ color: '#d93025', marginBottom: '16px' }}>{error}</div>}

      <h2>Платежи</h2>
      {payments.length === 0 ? (
        <p style={{ color: '#666' }}>Нет платежей</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
              <th style={{ padding: '8px' }}>Сумма</th>
              <th style={{ padding: '8px' }}>Статус</th>
              <th style={{ padding: '8px' }}>Дата</th>
            </tr>
          </thead>
          <tbody>
            {payments.map((p) => (
              <tr key={p.id} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '8px' }}>{p.amount} ₽</td>
                <td style={{ padding: '8px', color: STATUS_COLORS[p.status] }}>
                  {STATUS_LABELS[p.status] || p.status}
                </td>
                <td style={{ padding: '8px', color: '#666' }}>
                  {new Date(p.created_at).toLocaleString('ru-RU')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}
