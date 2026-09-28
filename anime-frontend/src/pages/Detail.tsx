import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { AnimeCard } from '../components/AnimeCard';
import { genreVi, seasonVi, statusVi } from '../i18n/genres';
import type { AnimeDetail, AnimeMini } from '../types/anime';

export function Detail() {
  const { id } = useParams();
  const { data } = useQuery({ queryKey: ['anime', id], queryFn: async () => (await api.get<AnimeDetail>(`/api/v1/anime/${id}`)).data });
  const recs = useQuery({ queryKey: ['recs', id], queryFn: async () => (await api.get<AnimeMini[]>(`/api/v1/anime/${id}/recommendations`)).data });
  if (!data) return <p className="p-4">Đang tải…</p>;
  const meta = [
    data.score != null && `Điểm ${data.score}`,
    data.year ?? null,
    seasonVi(data.season),
    statusVi(data.status),
    data.episodes != null && `${data.episodes} tập`,
    data.source ?? null,
    ...(data.studios ?? []),
  ].filter(Boolean) as string[];
  return (
    <main className="p-4">
      <div className="flex gap-4 mb-4">
        {data.image_url && (
          <img src={data.image_url} alt={data.title} loading="lazy" className="w-40 rounded object-cover self-start" />
        )}
        <div>
          <h1 className="text-2xl">{data.title}</h1>
          {data.title_japanese && <p className="text-anilist-textMuted">{data.title_japanese}</p>}
          <p className="text-sm text-anilist-textMuted mt-1">{meta.join(' · ')}</p>
          <div className="flex flex-wrap gap-1 mt-2">
            {(data.genres ?? []).map((g) => (
              <Link key={g} to={`/genre/${encodeURIComponent(g)}`} className="text-xs border border-anilist-border rounded px-2 py-0.5 hover:border-anilist-accent">{genreVi(g)}</Link>
            ))}
          </div>
        </div>
      </div>
      <p className="text-anilist-textMuted">{data.synopsis}</p>
      <div className="flex flex-wrap gap-1 mt-2">{(data.tags ?? []).map((t) => <span key={t.name} className="text-xs border border-anilist-border rounded px-2 py-0.5">{t.name} {t.weight}%</span>)}</div>
      <h2 className="mt-4 mb-2">Gợi ý liên quan</h2>
      <div className="flex gap-2 overflow-x-auto">{(recs.data ?? []).map((a) => <div key={a.id} className="min-w-40"><AnimeCard a={a} why="Thể loại tương tự" /></div>)}</div>
    </main>
  );
}
