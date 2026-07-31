import type { Asset } from "./asset";

export interface WatchlistItem {
  id: number;
  note: string;
  asset: Asset;
}

export interface Watchlist {
  id: number;
  name: string;
  items: WatchlistItem[];
}
