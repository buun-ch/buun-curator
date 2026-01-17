import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { discoverFeeds } from "@/lib/feed-discovery";

describe("feed-discovery", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("discoverFeeds", () => {
    describe("direct feed URL detection", () => {
      it("detects RSS feed with plain text title", async () => {
        const rssXml = `<?xml version="1.0" encoding="UTF-8"?>
          <rss version="2.0">
            <channel>
              <title>My RSS Feed</title>
              <link>https://example.com</link>
              <description>A test feed</description>
            </channel>
          </rss>`;

        // HEAD request returns XML content type
        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "application/rss+xml" }),
        });
        // GET request returns feed content
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(rssXml),
        });

        const result = await discoverFeeds("https://example.com/feed.xml");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].title).toBe("My RSS Feed");
        expect(result.feeds[0].type).toBe("rss");
        expect(result.siteTitle).toBe("My RSS Feed");
      });

      it("detects RSS feed with CDATA title", async () => {
        const rssXml = `<?xml version="1.0" encoding="UTF-8"?>
          <rss version="2.0">
            <channel>
              <title><![CDATA[My CDATA Feed Title]]></title>
              <link>https://example.com</link>
            </channel>
          </rss>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "application/rss+xml" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(rssXml),
        });

        const result = await discoverFeeds("https://example.com/feed");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].title).toBe("My CDATA Feed Title");
        expect(result.siteTitle).toBe("My CDATA Feed Title");
      });

      it("detects Atom feed with title", async () => {
        const atomXml = `<?xml version="1.0" encoding="UTF-8"?>
          <feed xmlns="http://www.w3.org/2005/Atom">
            <title>My Atom Feed</title>
            <link href="https://example.com"/>
          </feed>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "application/atom+xml" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(atomXml),
        });

        const result = await discoverFeeds("https://example.com/atom.xml");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].title).toBe("My Atom Feed");
        expect(result.feeds[0].type).toBe("atom");
      });

      it("detects RSS feed from content when content-type is text/html", async () => {
        const rssXml = `<?xml version="1.0" encoding="UTF-8"?>
          <rss version="2.0">
            <channel>
              <title>Hidden RSS Feed</title>
              <link>https://example.com</link>
            </channel>
          </rss>`;

        // HEAD returns text/html
        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        // GET returns RSS content
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(rssXml),
        });

        const result = await discoverFeeds("https://example.com/feed");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].title).toBe("Hidden RSS Feed");
        expect(result.feeds[0].type).toBe("rss");
      });

      it("detects Atom feed from content", async () => {
        const atomXml = `<?xml version="1.0" encoding="UTF-8"?>
          <feed xmlns="http://www.w3.org/2005/Atom">
            <title>Hidden Atom Feed</title>
          </feed>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(atomXml),
        });

        const result = await discoverFeeds("https://example.com/feed");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].title).toBe("Hidden Atom Feed");
        expect(result.feeds[0].type).toBe("atom");
      });
    });

    describe("HTML page feed discovery", () => {
      it("extracts feed links from HTML page", async () => {
        const html = `<!DOCTYPE html>
          <html>
          <head>
            <title>My Website</title>
            <link rel="alternate" type="application/rss+xml" title="RSS Feed" href="/feed.xml" />
            <link rel="alternate" type="application/atom+xml" title="Atom Feed" href="/atom.xml" />
          </head>
          <body></body>
          </html>`;

        // HEAD returns text/html (not a feed)
        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        // GET returns HTML (not RSS/Atom content)
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(html),
        });
        // Fetch the HTML page
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(html),
        });

        const result = await discoverFeeds("https://example.com");

        expect(result.feeds).toHaveLength(2);
        expect(result.feeds[0].url).toBe("https://example.com/feed.xml");
        expect(result.feeds[0].title).toBe("RSS Feed");
        expect(result.feeds[0].type).toBe("rss");
        expect(result.feeds[1].url).toBe("https://example.com/atom.xml");
        expect(result.feeds[1].title).toBe("Atom Feed");
        expect(result.feeds[1].type).toBe("atom");
        expect(result.siteTitle).toBe("My Website");
      });

      it("handles relative feed URLs", async () => {
        const html = `<!DOCTYPE html>
          <html>
          <head>
            <title>Test Site</title>
            <link rel="alternate" type="application/rss+xml" href="feed.xml" />
          </head>
          </html>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(html),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(html),
        });

        const result = await discoverFeeds("https://example.com/blog/");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].url).toBe("https://example.com/blog/feed.xml");
      });
    });

    describe("URL normalization", () => {
      it("adds https:// prefix if missing", async () => {
        const rssXml = `<?xml version="1.0"?>
          <rss version="2.0">
            <channel>
              <title>Test</title>
            </channel>
          </rss>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "application/rss+xml" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(rssXml),
        });

        const result = await discoverFeeds("example.com/feed");

        expect(result.feeds[0].url).toBe("https://example.com/feed");
        expect(result.siteUrl).toBe("https://example.com");
      });

      it("preserves http:// prefix", async () => {
        const rssXml = `<?xml version="1.0"?>
          <rss version="2.0">
            <channel>
              <title>Test</title>
            </channel>
          </rss>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "application/rss+xml" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(rssXml),
        });

        const result = await discoverFeeds("http://example.com/feed");

        expect(result.feeds[0].url).toBe("http://example.com/feed");
        expect(result.siteUrl).toBe("http://example.com");
      });
    });

    describe("common feed paths fallback", () => {
      it("tries common feed paths when no feeds found in HTML", async () => {
        const htmlWithoutFeeds = `<!DOCTYPE html>
          <html>
          <head><title>No Feed Links</title></head>
          <body></body>
          </html>`;

        const rssXml = `<?xml version="1.0"?>
          <rss version="2.0">
            <channel>
              <title>Found via common path</title>
            </channel>
          </rss>`;

        // Initial HEAD check - not a feed
        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        // Initial GET check - HTML content, not a feed
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(htmlWithoutFeeds),
        });
        // Fetch HTML page for link extraction
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(htmlWithoutFeeds),
        });

        // Common paths probing - /feed returns RSS
        mockFetch.mockImplementation((url: string, options?: RequestInit) => {
          if (options?.method === "HEAD") {
            if (url === "https://example.com/feed") {
              return Promise.resolve({
                headers: new Headers({ "content-type": "application/rss+xml" }),
              });
            }
            return Promise.resolve({
              headers: new Headers({ "content-type": "text/html" }),
            });
          }
          if (url === "https://example.com/feed") {
            return Promise.resolve({
              ok: true,
              text: () => Promise.resolve(rssXml),
            });
          }
          return Promise.resolve({
            ok: true,
            text: () => Promise.resolve(htmlWithoutFeeds),
          });
        });

        const result = await discoverFeeds("https://example.com");

        expect(result.feeds.length).toBeGreaterThan(0);
        expect(result.siteTitle).toBe("No Feed Links");
      });
    });

    describe("error handling", () => {
      it("returns empty feeds on fetch error", async () => {
        mockFetch.mockRejectedValue(new Error("Network error"));

        const result = await discoverFeeds("https://example.com");

        expect(result.feeds).toHaveLength(0);
        expect(result.siteUrl).toBe("https://example.com");
      });

      it("returns empty feeds on HTTP error", async () => {
        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve("<html></html>"),
        });
        mockFetch.mockResolvedValueOnce({
          ok: false,
          status: 404,
        });

        const result = await discoverFeeds("https://example.com");

        expect(result.feeds).toHaveLength(0);
      });
    });

    describe("feed type detection", () => {
      it("detects RSS type from content-type header", async () => {
        const rssXml = `<rss version="2.0"><channel><title>RSS</title></channel></rss>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "application/rss+xml; charset=utf-8" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(rssXml),
        });

        const result = await discoverFeeds("https://example.com/feed");

        expect(result.feeds[0].type).toBe("rss");
      });

      it("detects Atom type from content-type header", async () => {
        const atomXml = `<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom</title></feed>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "application/atom+xml" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(atomXml),
        });

        const result = await discoverFeeds("https://example.com/atom");

        expect(result.feeds[0].type).toBe("atom");
      });

      it("detects type from URL when content-type is generic XML", async () => {
        const rssXml = `<rss version="2.0"><channel><title>RSS</title></channel></rss>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "application/xml" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(rssXml),
        });

        const result = await discoverFeeds("https://example.com/rss.xml");

        expect(result.feeds[0].type).toBe("rss");
      });
    });

    describe("Medium-specific feed discovery", () => {
      it("discovers feed for Medium user profile URL", async () => {
        const mediumRss = `<?xml version="1.0" encoding="UTF-8"?>
          <rss version="2.0">
            <channel>
              <title>Michael Landis on Medium</title>
              <link>https://medium.com/@michaellandis</link>
            </channel>
          </rss>`;

        // Initial HEAD check - not a feed (user profile page)
        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        // Initial GET check - HTML content, not a feed
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve("<html><body>Profile page</body></html>"),
        });
        // Medium feed URL HEAD check
        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/xml; charset=UTF-8" }),
        });
        // Medium feed URL GET for title extraction
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(mediumRss),
        });

        const result = await discoverFeeds("https://medium.com/@michaellandis");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].url).toBe("https://medium.com/feed/@michaellandis");
        expect(result.feeds[0].title).toBe("Michael Landis on Medium");
        expect(result.siteUrl).toBe("https://medium.com");
      });

      it("discovers feed for Medium publication URL", async () => {
        const mediumRss = `<?xml version="1.0" encoding="UTF-8"?>
          <rss version="2.0">
            <channel>
              <title>Towards Data Science</title>
              <link>https://towardsdatascience.com</link>
            </channel>
          </rss>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve("<html></html>"),
        });
        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/xml" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(mediumRss),
        });

        const result = await discoverFeeds("https://medium.com/towards-data-science");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].url).toBe("https://medium.com/feed/towards-data-science");
      });

      it("handles Medium URL with trailing slash", async () => {
        const mediumRss = `<?xml version="1.0"?>
          <rss version="2.0">
            <channel><title>Test</title></channel>
          </rss>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve("<html></html>"),
        });
        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/xml" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(mediumRss),
        });

        const result = await discoverFeeds("https://medium.com/@username/");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].url).toBe("https://medium.com/feed/@username");
      });

      it("does not apply Medium logic to non-Medium URLs", async () => {
        const html = `<!DOCTYPE html>
          <html>
          <head>
            <title>Other Site</title>
            <link rel="alternate" type="application/rss+xml" href="/feed.xml" />
          </head>
          </html>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(html),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(html),
        });

        const result = await discoverFeeds("https://example.com/@username");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].url).toBe("https://example.com/feed.xml");
      });

      it("does not apply Medium logic to medium.com root URL", async () => {
        const html = `<!DOCTYPE html>
          <html>
          <head><title>Medium</title></head>
          </html>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(html),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(html),
        });

        // Mock common paths - none succeed
        mockFetch.mockImplementation(() =>
          Promise.resolve({
            headers: new Headers({ "content-type": "text/html" }),
            ok: true,
            text: () => Promise.resolve(html),
          })
        );

        const result = await discoverFeeds("https://medium.com/");

        // should not find /feed/ since root path is skipped
        expect(result.feeds.filter((f) => f.url === "https://medium.com/feed/")).toHaveLength(0);
      });

      it("skips Medium feed URL if already a feed URL", async () => {
        const mediumRss = `<?xml version="1.0"?>
          <rss version="2.0">
            <channel><title>Direct Feed</title></channel>
          </rss>`;

        // Direct feed URL detection
        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/xml" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(mediumRss),
        });

        const result = await discoverFeeds("https://medium.com/feed/@username");

        expect(result.feeds).toHaveLength(1);
        expect(result.feeds[0].url).toBe("https://medium.com/feed/@username");
        expect(result.feeds[0].title).toBe("Direct Feed");
      });
    });

    describe("real-world feed formats", () => {
      it("handles WordPress RSS feed with CDATA", async () => {
        const wpRss = `<?xml version="1.0" encoding="UTF-8"?>
          <rss version="2.0"
            xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:atom="http://www.w3.org/2005/Atom">
            <channel>
              <title><![CDATA[DevelopersIO | Tech Blog]]></title>
              <atom:link href="https://dev.classmethod.jp/feed/" rel="self" type="application/rss+xml" />
              <link>https://dev.classmethod.jp</link>
              <description><![CDATA[Tech articles]]></description>
            </channel>
          </rss>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "application/rss+xml; charset=UTF-8" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(wpRss),
        });

        const result = await discoverFeeds("https://dev.classmethod.jp/feed/");

        expect(result.feeds[0].title).toBe("DevelopersIO | Tech Blog");
        expect(result.siteTitle).toBe("DevelopersIO | Tech Blog");
      });

      it("handles RDF/RSS 1.0 format", async () => {
        const rdfRss = `<?xml version="1.0" encoding="UTF-8"?>
          <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                   xmlns="http://purl.org/rss/1.0/">
            <channel>
              <title>RDF Feed Title</title>
              <link>https://example.com</link>
            </channel>
          </rdf:RDF>`;

        mockFetch.mockResolvedValueOnce({
          headers: new Headers({ "content-type": "text/html" }),
        });
        mockFetch.mockResolvedValueOnce({
          ok: true,
          text: () => Promise.resolve(rdfRss),
        });

        const result = await discoverFeeds("https://example.com/rdf");

        expect(result.feeds[0].title).toBe("RDF Feed Title");
        expect(result.feeds[0].type).toBe("rss");
      });
    });
  });
});
