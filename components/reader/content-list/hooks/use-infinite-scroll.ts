import { useEffect, useRef } from "react";

interface UseInfiniteScrollOptions {
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore?: () => void;
}

/**
 * Hook for infinite scroll using IntersectionObserver.
 *
 * @param options - Hook options
 * @returns Ref to attach to the sentinel element
 */
export function useInfiniteScroll({
  hasMore,
  loadingMore,
  onLoadMore,
}: UseInfiniteScrollOptions) {
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!hasMore || !onLoadMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loadingMore) {
          onLoadMore();
        }
      },
      { threshold: 0.1 }
    );

    const currentRef = loadMoreRef.current;
    if (currentRef) {
      observer.observe(currentRef);
    }

    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
    };
  }, [hasMore, loadingMore, onLoadMore]);

  return loadMoreRef;
}
