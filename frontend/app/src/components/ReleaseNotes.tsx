import ReactMarkdown from "react-markdown"

interface ReleaseNotesProps {
  content: string
}

export function ReleaseNotes({ content }: ReleaseNotesProps) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:text-foreground prose-headings:font-semibold prose-h1:text-base prose-h2:text-sm prose-h3:text-sm prose-p:text-muted-foreground prose-p:leading-relaxed prose-strong:text-foreground prose-strong:font-semibold prose-ul:text-muted-foreground prose-ol:text-muted-foreground prose-li:text-muted-foreground prose-li:my-1 prose-ul:pl-4 prose-ol:pl-4 prose-li:pl-1">
      <ReactMarkdown
        components={{
          h1: ({ children }) => (
            <h1 className="text-base font-semibold text-foreground mb-2">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-sm font-semibold text-foreground mb-2">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold text-foreground mb-1">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="text-muted-foreground leading-relaxed mb-2">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-4 text-muted-foreground space-y-1">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-4 text-muted-foreground space-y-1">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="text-muted-foreground">{children}</li>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-foreground">
              {children}
            </strong>
          ),
          em: ({ children }) => (
            <em className="italic text-muted-foreground">{children}</em>
          ),
          a: ({ children }) => (
            <span className="text-foreground">{children}</span>
          ),
          code: ({ children }) => (
            <code className="bg-background px-1 py-0.5 rounded text-xs font-mono text-foreground">
              {children}
            </code>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
