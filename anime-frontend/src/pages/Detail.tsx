import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { AnimeCard } from '../components/AnimeCard';
import type { AnimeDetail, AnimeMini } from '../types/anime';

export function Detail() {
  const { id } = useParams();
  const { data } = useQuery({ queryKey: ['anime', id], queryFn: async () => (await api.get<AnimeDetail>(`/api/v1/anime/${id}`)).data });
  const recs = useQuery({ queryKey: ['recs', id], queryFn: async () => (await api.get<AnimeMini[]>(`/api/v1/anime/${id}/recommendations`)).data });
  if (!data) return <p className="p-4">Loading…</p>;
  return (
    <main className="p-4">
      <h1 className="text-2xl">{data.title}</h1>
      <p className="text-anilist-textMuted">{data.synopsis}</p>
      <div className="flex flex-wrap gap-1 mt-2">{data.tags.map((t) => <span key={t.name} className="text-xs border border-anilist-border rounded px-2 py-0.5">{t.name} {t.weight}%</span>)}</div>
      <h2 className="mt-4 mb-2">Recommendations</h2>
      <div className="flex gap-2 overflow-x-auto">{(recs.data ?? []).map((a) => <div key={a.id} className="min-w-40"><AnimeCard a={a} why="Similar genres" /></div>)}</div>
    </main>
  );
}
