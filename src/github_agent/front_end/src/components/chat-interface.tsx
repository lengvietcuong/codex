"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  thinking?: string
}

interface ChatInterfaceProps {
  onResponse: (responseData: any) => void
  currentRepo?: string
  currentFiles?: string[]
}

export function ChatInterface({ onResponse, currentRepo, currentFiles }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [abortController, setAbortController] = useState<AbortController | null>(null)
  const [expandedThinking, setExpandedThinking] = useState<Record<string, boolean>>({})
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Generate a session ID if needed (in a real app, this would be handled better)
  useEffect(() => {
    const existingSessionId = localStorage.getItem("session_id")
    if (!existingSessionId) {
      const newSessionId = Math.random().toString(36).substring(2, 15)
      localStorage.setItem("session_id", newSessionId)
    }
  }, [])

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const toggleThinking = (messageId: string) => {
    setExpandedThinking((prev) => ({
      ...prev,
      [messageId]: !prev[messageId],
    }))
  }

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return

    // Cancel any ongoing request
    if (abortController) {
      abortController.abort()
    }

    const query = input.trim()
    const messageId = Date.now().toString()
    const responseId = `response-${messageId}`

    // Add user message to messages array
    setMessages((prev) => [
      ...prev, 
      { id: messageId, role: "user", content: query }
    ])

    // Immediately add a placeholder assistant message that will be updated
    setMessages((prev) => [
      ...prev,
      { id: responseId, role: "assistant", content: "", thinking: "" }
    ])

    setInput("")
    setIsLoading(true)
    setError(null)

    // Create a new AbortController for this request
    const controller = new AbortController()
    setAbortController(controller)

    try {
      // Get the session ID
      const sessionId = localStorage.getItem("session_id") || Math.random().toString(36).substring(2, 15)

      // Prepare the context with current repo and files
      const context: any = {}
      if (currentRepo) context.current_repo = currentRepo
      if (currentFiles && currentFiles.length > 0) context.current_files = currentFiles

      // Make the API call
      const response = await fetch("/api/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, query, context }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const errorData = await response.json()
        let errorMessage = `Error ${response.status}: ${errorData.error || "Unknown error"}`

        if (response.status === 503) {
          errorMessage = `${errorData.message || "Backend server unavailable"}\n\nPlease make sure the Python backend is running with:\n\npython api.py`
        }

        throw new Error(errorMessage)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error("Failed to get reader from response")

      let responseContent = ""
      let thinkingContent = ""

      // Process the stream
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const events = chunk.split("\n\n").filter(Boolean)

        for (const event of events) {
          if (event.startsWith("data: ")) {
            try {
              const jsonContent = event.slice(6) // Remove "data: " prefix
              const parsedData = JSON.parse(jsonContent)

              if (parsedData.action_type === "error") {
                console.error("Stream error:", parsedData.content)
                responseContent += "\n" + parsedData.content
              } else if (parsedData.action_type === "thinking") {
                // Append to thinking content
                thinkingContent += parsedData.content
              } else if (parsedData.action_type === "self_solve") {
                // For self_solve, add to the response content
                responseContent += parsedData.content
              }

              // Update the assistant message in the messages array
              setMessages((prev) => prev.map(msg => 
                msg.id === responseId 
                  ? { ...msg, content: responseContent, thinking: thinkingContent }
                  : msg
              ))

              // Pass the structured response data to parent component
              onResponse(parsedData)
            } catch (e) {
              console.error("Error parsing stream data:", e, event)
            }
          }
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        console.log("Request was cancelled")
      } else {
        console.error("Error processing message:", error)
        setError(error instanceof Error ? error.message : String(error))
        
        // Update the assistant message with the error
        setMessages((prev) => prev.map(msg => 
          msg.id === responseId 
            ? { ...msg, content: "Sorry, an error occurred while generating a response." }
            : msg
        ))
      }
    } finally {
      setAbortController(null)
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // Debugging useEffect
  useEffect(() => {
    console.log("Messages updated:", messages)
  }, [messages])

  return (
    <div className="flex flex-col h-full">
      <ScrollArea className="flex-1 p-4 overflow-auto">
        <div className="space-y-4">
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Connection Error</AlertTitle>
              <AlertDescription className="whitespace-pre-line">{error}</AlertDescription>
            </Alert>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={`p-3 rounded-lg ${
                message.role === "user" ? "bg-primary text-primary-foreground ml-8" : "bg-muted mr-8"
              }`}
            >
              <div className="text-sm font-medium mb-1">{message.role === "user" ? "You" : "Assistant"}</div>

              {message.role === "assistant" && message.thinking && (
                <div className="mb-3">
                  <div className="flex items-center text-xs text-muted-foreground mb-1">
                    <button
                      onClick={() => toggleThinking(message.id)}
                      className="flex items-center hover:text-foreground transition-colors"
                    >
                      {expandedThinking[message.id] ? (
                        <ChevronDown className="h-3 w-3 mr-1" />
                      ) : (
                        <ChevronRight className="h-3 w-3 mr-1" />
                      )}
                      Agent Thinking
                    </button>
                  </div>

                  {expandedThinking[message.id] && (
                    <pre className="text-xs overflow-auto bg-secondary/50 p-2 rounded whitespace-pre-wrap">
                      {message.thinking}
                    </pre>
                  )}
                </div>
              )}

              <div className="whitespace-pre-wrap">
                {message.content || (message.role === "assistant" && isLoading && 
                  <div className="animate-pulse">Thinking...</div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      <div className="border-t p-4">
        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Ask a question..."
            disabled={isLoading}
            className="flex-1 min-h-[60px] max-h-[200px]"
          />
          <Button onClick={handleSendMessage} disabled={isLoading || !input.trim()} className="self-end" size="icon">
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}