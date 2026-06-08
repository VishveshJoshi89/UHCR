import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { MarkdownRenderer } from "../../components/MarkdownRenderer";
import { TableOfContents } from "../../components/TableOfContents";
import { useMarkdown } from "../../hooks/useMarkdown";
import { getMarkdownFile, getPageTitle } from "../../utils/navigation";
import type { Heading } from "../../types";
import "./DocPage.css";

export function DocPage() {
  const location = useLocation();
  const [headings, setHeadings] = useState<Heading[]>([]);

  const markdownFile = getMarkdownFile(location.pathname);
  const { content, loading, error } = useMarkdown(markdownFile);

  useEffect(() => {
    window.scrollTo(0, 0);

    if (!location.hash) {
      return;
    }

    const timer = window.setTimeout(() => {
      const element = document.getElementById(location.hash.slice(1));
      element?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);

    return () => window.clearTimeout(timer);
  }, [location.pathname, location.hash]);

  useEffect(() => {
    document.title = `${getPageTitle(location.pathname)} - UHCR Documentation`;
  }, [location.pathname]);

  if (loading) {
    return (
      <div className="doc-page">
        <div className="doc-content">
          <div className="loading-skeleton">
            <div className="skeleton-line skeleton-title" />
            <div className="skeleton-line skeleton-text" />
            <div className="skeleton-line skeleton-text" />
            <div className="skeleton-line skeleton-text short" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="doc-page">
        <div className="doc-content">
          <div className="error-message">
            <h2>Page Not Found</h2>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="doc-page">
      <div className="doc-content">
        <MarkdownRenderer content={content} onHeadingsExtracted={setHeadings} />
      </div>
      <TableOfContents headings={headings} />
    </div>
  );
}
