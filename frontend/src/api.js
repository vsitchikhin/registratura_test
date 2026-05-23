const API = '/api'

export async function getWallet() {
  const res = await fetch(`${API}/wallet/`)
  return res.json()
}

export async function getPayments() {
  const res = await fetch(`${API}/payments/`)
  return res.json()
}

export async function createPayment(amount) {
  const res = await fetch(`${API}/payments/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount }),
  })
  if (!res.ok) {
    const data = await res.json()
    throw new Error(data.amount?.[0] || 'Ошибка создания платежа')
  }
  return res.json()
}
