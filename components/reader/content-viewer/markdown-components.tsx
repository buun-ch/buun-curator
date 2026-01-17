import type { Components } from "react-markdown";

/**
 * Custom components for ReactMarkdown to handle edge cases.
 */
export const markdownComponents: Components = {
  // Open external links in new window
  a: ({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
        {children}
      </a>
    );
  },
  // Filter out images with empty src to avoid browser warnings
  // Center images horizontally
  img: ({
    src,
    alt,
    ...props
  }: React.ImgHTMLAttributes<HTMLImageElement>) => {
    if (!src) return null;
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt || ""} className="mx-auto" {...props} />;
  },
};
