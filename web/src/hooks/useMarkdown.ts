import { useEffect, useState } from "react";

interface UseMarkdownResult {
  content: string;
  loading: boolean;
  error: string | null;
}

export function useMarkdown(filePath: string | undefined): UseMarkdownResult {
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(Boolean(filePath));
  const [error, setError] = useState<string | null>(
    filePath ? null : "No file path provided",
  );

  useEffect(() => {
    if (!filePath) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    async function loadMarkdown() {
      setLoading(true);
      setError(null);
      setContent("");

      try {
        if (!filePath) {
          return;
        }

        const response = await fetch(filePath, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Failed to load ${filePath}: ${response.statusText}`);
        }

        const text = await response.text();

        if (active) {
          setContent(text);
        }
      } catch (err) {
        if (!active || controller.signal.aborted) {
          return;
        }

        setError(
          err instanceof Error ? err.message : "Failed to load markdown",
        );
      } finally {
        if (active && !controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadMarkdown();

    return () => {
      active = false;
      controller.abort();
    };
  }, [filePath]);

  if (!filePath) {
    return {
      content: "",
      loading: false,
      error: "No file path provided",
    };
  }

  return { content, loading, error };
}
