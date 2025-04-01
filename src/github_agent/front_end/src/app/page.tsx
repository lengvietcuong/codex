"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { ResizableLayout } from "@/components/resizable-layout"
import { FileExplorer } from "@/components/file-explorer"
import { ContentViewer } from "@/components/content-viewer"
import { ChatInterface } from "@/components/chat-interface"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { X } from "lucide-react"
import { VerticalResizable } from "@/components/vertical-resizable"

interface Tab {
  id: string
  title: string
  type: "file" | "chart"
  content: string
  repoName?: string
  path?: string
}

export default function GitHubAIPage() {
  const [currentRepo, setCurrentRepo] = useState("")
  const [fileStructure, setFileStructure] = useState<any[]>([])
  const [tabs, setTabs] = useState<Tab[]>([])
  const [activeTab, setActiveTab] = useState<string | null>(null)
  const [currentFiles, setCurrentFiles] = useState<string[]>([])

  // Handle file selection from FileExplorer
  const handleFileSelect = async (repo: string, path: string) => {
    // Try to find if we already have this file open
    const existingTabId = tabs.find((t) => t.type === "file" && t.repoName === repo && t.path === path)?.id

    if (existingTabId) {
      setActiveTab(existingTabId)
      return
    }

    // Create a new tab for this file with loading state
    const newTabId = `file-${Date.now()}`
    const fileTab: Tab = {
      id: newTabId,
      title: path.split("/").pop() || path,
      type: "file",
      content: "Loading...",
      repoName: repo,
      path: path,
    }

    setTabs((prev) => [...prev, fileTab])
    setActiveTab(newTabId)

    // Track this file in our current files list
    setCurrentFiles((prev) => {
      if (!prev.includes(path)) {
        return [...prev, path]
      }
      return prev
    })

    try {
      // Generate a session ID if needed
      const sessionId = localStorage.getItem("session_id") || Math.random().toString(36).substring(7)
      localStorage.setItem("session_id", sessionId)

      // Update the current repository context
      setCurrentRepo(repo)

      // Cleanup repo path if needed (e.g. "owner/repo/owner/repo" -> "owner/repo")
      const cleanRepoPath =
        repo.includes("/") && repo.split("/").length > 2 ? `${repo.split("/")[0]}/${repo.split("/")[1]}` : repo

      // Fetch the file content
      const encodedPath = encodeURIComponent(path)
      const response = await fetch(`/api/file/${sessionId}/${cleanRepoPath}/${encodedPath}`, {
        method: "GET",
        headers: {
          "Cache-Control": "no-cache",
        },
      })

      const data = await response.json()

      if (data.error) {
        throw new Error(data.error)
      }

      // Update the tab with the actual content
      setTabs((prev) =>
        prev.map((tab) =>
          tab.id === newTabId ? { ...tab, content: data.content || "File content unavailable" } : tab,
        ),
      )
    } catch (error) {
      console.error("Failed to load file:", error)

      // Update the tab with error message
      setTabs((prev) =>
        prev.map((tab) =>
          tab.id === newTabId
            ? {
                ...tab,
                content: `Error loading file content: ${error instanceof Error ? error.message : "Unknown error"}`,
              }
            : tab,
        ),
      )
    }
  }

  // Handle response from ChatInterface
  const handleChatResponse = (response: any) => {
    const actionType = response.action_type || "self_solve"

    // Handle different action types
    if (actionType === "search") {
      if (response.repositories) {
        setFileStructure(response.repositories)
        // Don't set current repo yet as user needs to select one
      }
    } else if (["list_directory", "repo_tree", "clone"].includes(actionType)) {
      if (response.fileStructure) {
        setFileStructure(response.fileStructure)
        if (response.repoName) {
          setCurrentRepo(response.repoName)
          // When changing repos, reset the current files
          setCurrentFiles([])
        }
      }
    } else if (actionType === "read_file") {
      // Check if we already have this file open
      const existingTabId = tabs.find(
        (t) => t.type === "file" && t.repoName === response.repoName && t.path === response.filePath,
      )?.id

      if (existingTabId) {
        setActiveTab(existingTabId)
        return
      }

      // Create a new tab for this file
      if (response.filePath) {
        const newTabId = `file-${Date.now()}`
        const fileTab: Tab = {
          id: newTabId,
          title: response.filePath.split("/").pop() || response.filePath,
          type: "file",
          content: response.fileContent || "Loading...",
          repoName: response.repoName,
          path: response.filePath,
        }

        setTabs((prev) => [...prev, fileTab])
        setActiveTab(newTabId)

        // Track this file in our current files list
        setCurrentFiles((prev) => {
          if (!prev.includes(response.filePath)) {
            return [...prev, response.filePath]
          }
          return prev
        })

        // Update current repo if needed
        if (response.repoName && !currentRepo) {
          setCurrentRepo(response.repoName)
        }
      }
    } else if (actionType === "chart") {
      if (response.chartContent) {
        // Check if we already have this chart open
        const chartTitle = `Chart: ${response.repoName || "Repo"}`
        const existingTabId = tabs.find(
          (t) => t.type === "chart" && t.title === chartTitle && t.content === response.chartContent,
        )?.id

        if (existingTabId) {
          setActiveTab(existingTabId)
          return
        }

        const newTabId = `chart-${Date.now()}`
        const chartTab: Tab = {
          id: newTabId,
          title: chartTitle,
          type: "chart",
          content: response.chartContent,
        }

        setTabs((prev) => [...prev, chartTab])
        setActiveTab(newTabId)
      }
    }
  }

  // Close a tab
  const handleCloseTab = (tabId: string, e: React.MouseEvent) => {
    e.stopPropagation()

    // Find if this is a file tab that we need to remove from current files
    const tab = tabs.find((t) => t.id === tabId)
    if (tab?.type === "file" && tab.path) {
      setCurrentFiles((prev) => prev.filter((path) => path !== tab.path))
    }

    setTabs((prev) => prev.filter((tab) => tab.id !== tabId))

    // If we're closing the active tab, select another one if available
    if (activeTab === tabId) {
      const remainingTabs = tabs.filter((tab) => tab.id !== tabId)
      if (remainingTabs.length > 0) {
        setActiveTab(remainingTabs[remainingTabs.length - 1].id)
      } else {
        setActiveTab(null)
      }
    }
  }

  // Create a welcome tab on first load
  useEffect(() => {
    const welcomeTab: Tab = {
      id: "welcome",
      title: "Welcome",
      type: "file",
      content: "# Welcome to GitHub AI Assistant\n\nUse the chat interface on the right to interact with repositories.",
    }

    setTabs([welcomeTab])
    setActiveTab("welcome")
  }, [])

  return (
    <div className="h-screen w-full bg-background">
      <ResizableLayout
        leftPanel={
          <VerticalResizable
            topPanel={
              <FileExplorer repoName={currentRepo} fileStructure={fileStructure} onFileSelect={handleFileSelect} />
            }
            bottomPanel={
              <Tabs value={activeTab || ""} onValueChange={setActiveTab} className="flex flex-col h-full">
                <div className="border-b bg-background z-10 sticky top-0">
                  <TabsList className="flex overflow-x-auto w-full h-auto py-1">
                    {tabs.map((tab) => (
                      <TabsTrigger key={tab.id} value={tab.id} className="flex items-center gap-1 min-w-max">
                        {tab.title}
                        <button
                          className="ml-1 rounded-full hover:bg-muted p-0.5"
                          onClick={(e) => handleCloseTab(tab.id, e)}
                        >
                          <X size={14} />
                        </button>
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </div>

                <div className="flex-1 overflow-auto relative">
                  {/* Tab Contents */}
                  {tabs.map((tab) => (
                    <TabsContent key={tab.id} value={tab.id} className="p-0 mt-0 h-full absolute inset-0">
                      <ContentViewer type={tab.type} content={tab.content} filePath={tab.path} />
                    </TabsContent>
                  ))}
                </div>
              </Tabs>
            }
            defaultTopHeight={40}
            minTopHeight={15}
            minBottomHeight={15}
          />
        }
        rightPanel={
          <div className="flex flex-col h-full">
            <ChatInterface onResponse={handleChatResponse} currentRepo={currentRepo} currentFiles={currentFiles} />
          </div>
        }
        defaultLeftWidth={50}
      />
    </div>
  )
}

