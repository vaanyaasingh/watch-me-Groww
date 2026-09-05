"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export function useInstruments() {
  return useQuery({ queryKey: ["instruments"], queryFn: api.listInstruments });
}

export function useWatchlist() {
  return useQuery({ queryKey: ["watchlist"], queryFn: api.getWatchlist });
}

export function useAddToWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.addToWatchlist,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      queryClient.invalidateQueries({ queryKey: ["attention-feed"] });
    },
  });
}

export function useRemoveFromWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.removeFromWatchlist,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      queryClient.invalidateQueries({ queryKey: ["attention-feed"] });
    },
  });
}

export function useAttentionFeed() {
  return useQuery({ queryKey: ["attention-feed"], queryFn: api.getAttentionFeed });
}

export function useDigest(instrumentId: string) {
  return useQuery({
    queryKey: ["digest", instrumentId],
    queryFn: () => api.getDigest(instrumentId),
    enabled: Boolean(instrumentId),
  });
}

export function useAlerts() {
  return useQuery({ queryKey: ["alerts"], queryFn: api.getAlerts });
}

export function useCreateAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useDeleteAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useSubscriptionWindows() {
  return useQuery({ queryKey: ["subscription-windows"], queryFn: api.getSubscriptionWindows });
}

export function useMarketOverview() {
  return useQuery({ queryKey: ["market-overview"], queryFn: api.getMarketOverview });
}

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: api.getMe });
}
