import { useQuery, UseQueryOptions, QueryKey } from "@tanstack/react-query";

export function usePollingQuery<TQueryFnData, TError = unknown, TData = TQueryFnData>(
  key: QueryKey,
  queryFn: () => Promise<TQueryFnData>,
  options?: UseQueryOptions<TQueryFnData, TError, TData>,
  interval = 2500,
) {
  return useQuery({
    queryKey: key,
    queryFn,
    refetchInterval: interval,
    refetchIntervalInBackground: true,
    ...options,
  });
}
