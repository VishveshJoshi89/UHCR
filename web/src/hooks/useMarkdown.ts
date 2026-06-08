import { useState, useEffect } from 'react';

interface UseMarkdownResult {
  content: string;
  loading: boolean;
  error: string | null;
}

export function useMarkdown(filePath: string | undefined): UseMarkdownResult {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!filePath) {
      setContent('');
      setLoading(false);
      setError('No file path provided');
      return;
    }

    let isMounted = true;

    async function loadMarkdown() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(filePath!);
        
        if (!response.ok) {
          throw new Error(`Failed to load ${filePath}: ${response.statusText}`);
        }

        const text = await response.text();
        
        if (isMounted) {
          setContent(text);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Failed to load markdown');
          setLoading(false);
        }
      }
    }

    loadMarkdown();

    return () => {
      isMounted = false;
    };
  }, [filePath]);

  return { content, loading, error };
}
