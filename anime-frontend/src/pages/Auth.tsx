import { useState } from 'react';
import { api } from '../api/client';
import { useAuthStore } from '../stores/authStore';

export function Auth() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const signin = useAuthStore((s) => s.signin);
  return (
    <main className="p-4 max-w-sm">
      <h1 className="text-xl mb-3">Sign in</h1>
      <form onSubmit={async (e) => { e.preventDefault(); const r = await api.post('/api/v1/auth/signin', { email, password }); signin(r.data.token); localStorage.setItem('token', r.data.token); }} className="flex flex-col gap-2">
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" className="bg-anilist-card border border-anilist-border rounded px-2 py-1" />
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="password" className="bg-anilist-card border border-anilist-border rounded px-2 py-1" />
        <button className="bg-anilist-accent rounded px-3 py-1">Sign in</button>
      </form>
    </main>
  );
}
