export interface AnimeMini { id: number; title: string; title_japanese?: string | null; image_url?: string | null; score?: number | null; year?: number | null; }
export interface TagWithWeight { name: string; weight: number; }
export interface AnimeDetail extends AnimeMini { synopsis?: string | null; episodes?: number | null; status?: string | null; season?: string | null; studios: string[]; source?: string | null; genres: string[]; tags: TagWithWeight[]; }
export type ListStatus = 'watching' | 'completed' | 'on_hold' | 'dropped' | 'plan_to_watch';
