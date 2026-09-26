import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState { token: string | null; signin: (t: string) => void; signout: () => void; }
export const useAuthStore = create<AuthState>()(
  persist((set) => ({ token: null, signin: (t) => set({ token: t }), signout: () => set({ token: null }) }),
    { name: 'auth' }),
);
