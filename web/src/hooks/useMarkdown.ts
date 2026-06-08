import { useEffect, useState } from 'react';

export function useMarkdown(filePath: string) {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {

    let cancelled = false;

    async function loadMarkdown() {

      if (!filePath) {
        if (!cancelled) {
          setError('No file path provided');
          setLoading(false);
        }
        return;
      }

      try {

        setLoading(true);
        setError(null);

        const response = await fetch(filePath);

        if (!response.ok) {
          throw new Error('Failed to load markdown');
        }

        const text = await response.text();

        if (!cancelled) {
          setContent(text);
        }

      } catch (err) {

        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unknown error'
          );
        }

      } finally {

        if (!cancelled) {
          setLoading(false);
        }

      }

    }

    loadMarkdown();

    return () => {
      cancelled = true;
    };

  }, [filePath]);

  return {
    content,
    loading,
    error
  };
}