import { create } from 'zustand';

interface AppState {
  profile: string;
  setProfile: (profile: string) => void;
  strategy: string;
  setStrategy: (strategy: string) => void;
}

export const useStore = create<AppState>((set) => ({
  profile: 'balanced',
  setProfile: (profile) => set({ profile }),
  strategy: 'threshold',
  setStrategy: (strategy) => set({ strategy }),
}));
