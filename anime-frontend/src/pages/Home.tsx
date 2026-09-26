import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { AnimeGrid } from '../components/AnimeCard';
import type { AnimeMini } from '../types/anime';

export function Home() {
  const { data } = useQuery({ queryKey: ['trending'], queryFn: async () => (await api.get<AnimeMini[]>('/api/v1/anime/trending')).data });
  return <main className="p-4"><h1 className="text-xl mb-3">This Season · Top Rated</h1><AnimeGrid items={data ?? []} /></main>;
}
