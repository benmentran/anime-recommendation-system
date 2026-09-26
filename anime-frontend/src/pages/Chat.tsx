import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { api } from '../api/client';

type Candidate = { mal_id: number; title: string; score?: number | null };
type AskResponse = { answer: string; candidates: Candidate[] };
type Msg = { role: 'user' | 'assistant'; text: string; candidates?: Candidate[] };

export function Chat() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Msg[]>([]);

  const ask = useMutation({
    mutationFn: async (query: string) => {
      const r = await api.post<AskResponse>('/api/v1/rag/ask', { query, k: 5 });
      return r.data;
    },
    onSuccess: (data) => {
      setMessages((m) => [...m,
        { role: 'assistant', text: data.answer, candidates: data.candidates }]);
    },
    onError: () => {
      setMessages((m) => [...m, { role: 'assistant',
        text: 'Xin lỗi, dịch vụ gợi ý hiện không khả dụng. Hãy thử lại sau.' }]);
    },
  });

  const send = (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || ask.isPending) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', text: q }]);
    ask.mutate(q);
  };

  return (
    <main className="max-w-2xl mx-auto p-4 flex flex-col gap-3" data-testid="chat-page">
      <h1 className="text-xl font-bold">Hỏi đáp Anime</h1>
      <div className="flex flex-col gap-3 min-h-[40vh]" data-testid="chat-messages">
        {messages.length === 0 && (
          <p className="text-anilist-textMuted" data-testid="chat-empty">
            Ví dụ: “anime mecha chính trị, nhân vật chính phản diện, nét vẽ hiện đại?”
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} data-testid={`chat-msg-${m.role}`}
            className={`p-3 rounded ${m.role === 'user'
              ? 'bg-anilist-accent/20 self-end' : 'bg-anilist-card self-start'} max-w-[90%]`}>
            <p className="whitespace-pre-wrap">{m.text}</p>
            {m.candidates && m.candidates.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2" data-testid="chat-candidates">
                {m.candidates.map((c) => (
                  <Link key={c.mal_id} to={`/anime/${c.mal_id}`}
                    data-testid={`chat-candidate-${c.mal_id}`}
                    className="text-sm underline text-anilist-accent">
                    {c.title}{c.score ? ` (${c.score})` : ''}
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}
        {ask.isPending && <p data-testid="chat-loading">Đang tìm...</p>}
      </div>
      <form onSubmit={send} className="flex gap-2" data-testid="chat-form">
        <input value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Hỏi về anime..." data-testid="chat-input"
          className="flex-1 p-2 rounded bg-anilist-card border border-anilist-border" />
        <button type="submit" disabled={ask.isPending} data-testid="chat-send"
          className="px-4 py-2 rounded bg-anilist-accent disabled:opacity-50">Gửi</button>
      </form>
    </main>
  );
}
