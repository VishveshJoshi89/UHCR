import { useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSlug from 'rehype-slug';
import rehypeSanitize from 'rehype-sanitize';
import { Link } from 'react-router-dom';
import { CodeBlock } from '../CodeBlock';
import type { Heading } from '../../types';
import './MarkdownRenderer.css';

interface MarkdownRendererProps {
  content: string;
  onHeadingsExtracted?: (headings: Heading[]) => void;
}

export function MarkdownRenderer({ content, onHeadingsExtracted }: MarkdownRendererProps) {
  useEffect(() => {
    if (onHeadingsExtracted) {
      // Extract headings from rendered content
      const headings: Heading[] = [];
      const container = document.querySelector('.markdown-content');
      
      if (container) {
        const headingElements = container.querySelectorAll('h2, h3');
        headingElements.forEach((el) => {
          const id = el.id || el.textContent?.toLowerCase().replace(/\s+/g, '-').replace(/[^\w-]/g, '') || '';
          if (!el.id) {
            el.id = id;
          }
          
          headings.push({
            id,
            text: el.textContent || '',
            level: parseInt(el.tagName[1]),
          });
        });
        
        onHeadingsExtracted(headings);
      }
    }
  }, [content, onHeadingsExtracted]);

  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSlug, rehypeSanitize]}
        components={{
          code(props) {
            const { children, className, ...rest } = props;
            const match = /language-(\w+)/.exec(className || '');
            return match ? (
              <CodeBlock className={className}>
                {String(children).replace(/\n$/, '')}
              </CodeBlock>
            ) : (
              <code className="inline-code" {...rest}>
                {children}
              </code>
            );
          },
          a({ href, children }) {
            // Convert relative .md links to application routes
            if (href?.endsWith('.md')) {
              const routePath = '/docs/' + href.replace('.md', '').replace(/^\.\.\//, '');
              return <Link to={routePath}>{children}</Link>;
            }
            
            // Handle anchor links
            if (href?.startsWith('#')) {
              return (
                <a href={href} onClick={(e) => {
                  e.preventDefault();
                  const element = document.getElementById(href.slice(1));
                  element?.scrollIntoView({ behavior: 'smooth' });
                }}>
                  {children}
                </a>
              );
            }
            
            // External links
            return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
          },
          img({ src, alt }) {
            return <img src={src} alt={alt} loading="lazy" />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
