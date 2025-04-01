"use client"

import { useEffect, useState, useRef } from "react"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "./ui/scroll-area"
import SyntaxHighlighter from "react-syntax-highlighter"
import { atomOneDark } from "react-syntax-highlighter/dist/esm/styles/hljs"
import { useTheme } from "next-themes"

interface ContentViewerProps {
  type: "file" | "chart"
  content: string
  filePath?: string
}

export function ContentViewer({ type, content, filePath }: ContentViewerProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const [isRendering, setIsRendering] = useState(false)
  const [isLoading, setIsLoading] = useState(content === "Loading...")
  const { resolvedTheme } = useTheme()

  // Determine language for syntax highlighting based on file extension
  const getLanguage = (path?: string): string => {
    if (!path) return "text"
    const extension = path.split(".").pop()?.toLowerCase() || ""
    const languageMap: Record<string, string> = {
      js: "javascript",
      jsx: "jsx",
      ts: "typescript",
      tsx: "tsx",
      py: "python",
      rb: "ruby",
      java: "java",
      c: "c",
      cpp: "cpp",
      cs: "csharp",
      go: "go",
      php: "php",
      html: "html",
      css: "css",
      json: "json",
      md: "markdown",
      yml: "yaml",
      yaml: "yaml",
      sh: "bash",
      bash: "bash",
      sql: "sql",
    }
    return languageMap[extension] || "text"
  }

  useEffect(() => {
    // Update loading state when content changes
    setIsLoading(content === "Loading...")

    if (type === "chart" && chartRef.current && content) {
      const renderChart = async () => {
        setIsRendering(true)
        try {
          // Dynamically import mermaid to avoid SSR issues
          const mermaidModule = await import("mermaid")
          const mermaid = mermaidModule.default

          // Initialize Mermaid with your configuration
          mermaid.initialize({
            startOnLoad: false,
            theme: resolvedTheme === "dark" ? "dark" : "default",
            securityLevel: "loose",
            flowchart: {
              htmlLabels: true,
              curve: "linear",
            },
            fontFamily: "sans-serif",
          })

          // Clear any previous content
          if (chartRef.current) {
            chartRef.current.innerHTML = ""
          }

          // Generate a unique ID for the diagram
          const uniqueId = `mermaid-${Date.now()}`

          // Render the diagram and get the SVG as a string
          const { svg } = await mermaid.render(uniqueId, content)
          console.log("Rendered mermaid chart:", svg)
          
          // Directly insert the SVG into the DOM without parsing
          if (chartRef.current && svg) {
            chartRef.current.innerHTML = svg
          }
        } catch (error) {
          console.error("Failed to render mermaid chart:", error)
          if (chartRef.current) {
            chartRef.current.innerHTML = `
              <div class="bg-red-50 dark:bg-red-900/20 p-4 rounded text-red-600 dark:text-red-400">
                <p class="font-medium">Error rendering chart</p>
                <p class="text-xs mt-2">${
                  error instanceof Error ? error.message : "Unknown error"
                }</p>
                <pre class="mt-2 text-xs overflow-auto">${content}</pre>
              </div>
            `
          }
        } finally {
          setIsRendering(false)
        }
      }

      renderChart()
    }
  }, [type, content, resolvedTheme])

  return (
    <ScrollArea className="h-full">
      <div className="p-4">
        {type === "file" && (
          <div>
            {filePath && (
              <div className="text-sm font-medium mb-2 text-muted-foreground">
                {filePath}
              </div>
            )}
            {isLoading ? (
              <div className="flex items-center justify-center p-12">
                <div className="space-y-2">
                  <Skeleton className="h-4 w-[250px]" />
                  <Skeleton className="h-4 w-[200px]" />
                  <Skeleton className="h-4 w-[300px]" />
                </div>
              </div>
            ) : content ? (
              <SyntaxHighlighter
                language={getLanguage(filePath)}
                style={atomOneDark}
                customStyle={{
                  borderRadius: "0.375rem",
                  padding: "1rem",
                  fontSize: "0.875rem",
                }}
              >
                {content}
              </SyntaxHighlighter>
            ) : (
              <div className="bg-muted p-4 rounded-md text-sm">
                No file content available
              </div>
            )}
          </div>
        )}

        {type === "chart" && (
          <div>
            <div className="text-sm font-medium mb-2 text-muted-foreground">
              Mermaid Chart
            </div>
            {isRendering ? (
              <div className="flex items-center justify-center p-12">
                <div className="space-y-2">
                  <Skeleton className="h-4 w-[250px]" />
                  <Skeleton className="h-4 w-[200px]" />
                  <Skeleton className="h-4 w-[300px]" />
                </div>
              </div>
            ) : (
              <div
                ref={chartRef}
                className="bg-card border rounded-md p-4 overflow-auto"
              >
                {!content && "No chart data available"}
              </div>
            )}
            {/* Display the source code below the chart */}
            {content && (
              <div className="mt-4">
                <div className="text-sm font-medium mb-2 text-muted-foreground">
                  Source Code
                </div>
                <SyntaxHighlighter
                  language="markdown"
                  style={atomOneDark}
                  customStyle={{
                    borderRadius: "0.375rem",
                    padding: "1rem",
                    fontSize: "0.875rem",
                  }}
                >
                  {content}
                </SyntaxHighlighter>
              </div>
            )}
          </div>
        )}
      </div>
    </ScrollArea>
  )
}
