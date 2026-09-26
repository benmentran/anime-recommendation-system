import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../api/client';
import type { ListStatus } from '../types/anime';

const TABS: ListStatus[] = ['watching', 'completed', 'on_hold', 'dropped', 'plan_to_watch'];

export function UserList() {
  const [tab, setTab] = useState<ListStatus>('watching');
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ['list'], queryFn: async () => (await api.get('/api/v1/list')).data });
  const patch = useMutation({ mutationFn: (v: { id: number; status: ListStatus }) => api.patch(`/api/v1/list/${v.id}`, { status: v.status }), onSettled: () => qc.invalidateQueries({ queryKey: ['list'] }) });
  const items = (data ?? []).filter((i: { status: string }) => i.status === tab);
  return (
    <main className="p-4">
      <div className="flex gap-2 mb-3">{TABS.map((t) => <button key={t} onClick={() => setTab(t)} className={t === tab ? 'bg-anilist-accent rounded px-2 py-1' : 'border border-anilist-border rounded px-2 py-1'}>{t}</button>)}</div>
      {items.map((i: { anime_id: number }) => (
        <div key={i.anime_id} className="flex gap-2 items-center border-b border-anilist-border py-2">
          <span className="flex-1">#{i.anime_id}</span>
          <select value={tab} onChange={(e) => patch.mutate({ id: i.anime_id, status: e.target.value as ListStatus })} className="bg-anilist-card border border-anilist-border rounded">
            {TABS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      ))}
    </main>
  );
}
