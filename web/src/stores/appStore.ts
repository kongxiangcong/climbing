import { create } from 'zustand'

interface AppState {
  selectedTicker: string
  setSelectedTicker: (ticker: string) => void
}

export const useAppStore = create<AppState>((set) => ({
  selectedTicker: '000725.SZ',
  setSelectedTicker: (ticker) => set({ selectedTicker: ticker }),
}))
