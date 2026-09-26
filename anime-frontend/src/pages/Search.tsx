import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { AnimeGrid } from '../components/AnimeCard';
import type { AnimeMini } from '../types/anime';

export function Search() {
  const [q, setQ] = useState('');
  const { data, refetch } = useQuery({ queryKey: ['search', q], enabled: false, queryFn: async () => (await api.get<AnimeMini[]>('/api/v1/anime/search', { params: { q } })).data });
  return (
    <main className="p-4">
      <form onSubmit={(e) => { e.preventDefault(); refetch(); }} className="flex gap-2 mb-3">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search anime…" className="bg-anilist-card border border-anilist-border rounded px-2 py-1 flex-1" />
        <button className="bg-anilist-accent rounded px-3">Search</button>
      </form>
      <AnimeGrid items={data ?? []} />
    </main>
  );
}
