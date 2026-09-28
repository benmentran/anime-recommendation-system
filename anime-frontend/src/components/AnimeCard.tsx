import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { AnimeMini } from '../types/anime';

export function AnimeCard({ a, why }: { a: AnimeMini; why?: string }) {
  const [imgOk, setImgOk] = useState(true);
  return (
    <Link to={`/anime/${a.id}`} className="rounded bg-anilist-card border border-anilist-border p-2 block">
      {a.image_url && imgOk ? (
        <img src={a.image_url} alt={a.title} loading="lazy" onError={() => setImgOk(false)} className="w-full aspect-[3/4] object-cover rounded mb-2" />
      ) : (
        <div className="w-full aspect-[3/4] rounded mb-2 bg-anilist-border flex items-center justify-center text-anilist-textMuted text-xs">Không có ảnh</div>
      )}
      <div className="font-medium truncate">{a.title}</div>
      <div className="text-sm text-anilist-textMuted">{a.score ?? '—'} · {a.year ?? '—'}</div>
      {why && <div className="text-xs mt-1 text-anilist-accent">{why}</div>}
    </Link>
  );
}

export function AnimeGrid({ items }: { items: AnimeMini[] }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
      {items.map((a) => <AnimeCard key={a.id} a={a} />)}
    </div>
  );
}
