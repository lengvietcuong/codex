"use client"

import { useState } from "react"
import { ChevronRight, ChevronDown, Folder, File, Code, Package } from "lucide-react"

interface FileExplorerProps {
  repoName: string
  fileStructure: any[]
  onFileSelect: (repo: string, path: string) => void
}

interface FileNode {
  name: string
  path: string
  type: "file" | "dir"
  size?: number
  children?: FileNode[]
}

export function FileExplorer({ repoName, fileStructure, onFileSelect }: FileExplorerProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  // Process the flat file structure into a nested one
  const processFileStructure = (files: any[]): FileNode[] => {
    if (!files || !Array.isArray(files)) return []
    
    // If this looks like search results with repository objects
    if (files.length > 0 && files[0].name && files[0].owner) {
      // This is a list of repositories
      return files.map(repo => ({
        name: repo.name,
        path: repo.name,
        type: "dir",
        children: processFileStructure(repo.contents_preview || [])
      }))
    }
    
    // Build a map for fast directory lookup
    const dirMap: Record<string, FileNode> = {}
    const rootNodes: FileNode[] = []
    
    // First pass: create all directory nodes
    for (const item of files) {
      const path = item.path || item.name || ''
      const name = item.name || path.split('/').pop() || ''
      const type = (item.type === 'dir' || item.type === 'directory') ? 'dir' : 'file'
      
      if (type === 'dir') {
        dirMap[path] = {
          name,
          path,
          type,
          children: []
        }
      }
    }
    
    // Second pass: process all files and organize them
    for (const item of files) {
      const path = item.path || item.name || ''
      const name = item.name || path.split('/').pop() || ''
      const type = (item.type === 'dir' || item.type === 'directory') ? 'dir' : 'file'
      
      // Skip directories as they were already created
      if (type === 'dir') continue
      
      // Create the file node
      const node: FileNode = {
        name,
        path,
        type,
        size: item.size
      }
      
      // Find parent directory
      const pathParts = path.split('/')
      pathParts.pop() // Remove filename
      const parentPath = pathParts.join('/')
      
      if (parentPath && dirMap[parentPath]) {
        // Add to parent directory
        dirMap[parentPath].children = dirMap[parentPath].children || []
        dirMap[parentPath].children!.push(node)
      } else {
        // Add to root if no parent found
        rootNodes.push(node)
      }
    }
    
    // Add all directory nodes to their parents or root
    for (const dirPath in dirMap) {
      const dir = dirMap[dirPath]
      const pathParts = dirPath.split('/')
      pathParts.pop() // Remove dirname
      const parentPath = pathParts.join('/')
      
      if (parentPath && dirMap[parentPath]) {
        // Add to parent directory
        dirMap[parentPath].children = dirMap[parentPath].children || []
        dirMap[parentPath].children!.push(dir)
      } else {
        // Add to root if no parent
        rootNodes.push(dir)
      }
    }
    
    // If this gives an empty result but we have raw files, fall back to simple mode
    if (rootNodes.length === 0 && files.length > 0) {
      return files.map(item => ({
        name: item.name || item.path?.split('/').pop() || '',
        path: item.path || item.name || '',
        type: (item.type === 'dir' || item.type === 'directory') ? 'dir' : 'file',
        size: item.size
      }))
    }
    
    return rootNodes
  }

  const toggleExpand = (path: string) => {
    setExpanded(prev => ({
      ...prev,
      [path]: !prev[path]
    }))
  }
  
  const renderFileIcon = (filename: string) => {
    // Determine file type by extension
    const extension = filename.split('.').pop()?.toLowerCase() || ''
    
    if (['js', 'jsx', 'ts', 'tsx'].includes(extension)) {
      return <Code className="h-4 w-4 text-yellow-500" />
    } else if (['json', 'md', 'yml', 'yaml'].includes(extension)) {
      return <File className="h-4 w-4 text-blue-500" />
    } else if (['py', 'rb', 'java', 'cpp', 'c', 'cs'].includes(extension)) {
      return <Code className="h-4 w-4 text-green-500" />
    } else if (['zip', 'tar', 'gz', 'rar'].includes(extension)) {
      return <Package className="h-4 w-4 text-purple-500" />
    } else {
      return <File className="h-4 w-4" />
    }
  }

  const renderFileTree = (nodes: FileNode[], depth: number = 0) => {
    return nodes.sort((a, b) => {
      // Sort by type (directories first) then by name
      if (a.type === 'dir' && b.type !== 'dir') return -1
      if (a.type !== 'dir' && b.type === 'dir') return 1
      return a.name.localeCompare(b.name)
    }).map((node) => {
      const isExpanded = expanded[node.path]
      const paddingLeft = `${depth * 16}px`
      
      if (node.type === 'dir') {
        return (
          <div key={node.path}>
            <div 
              className="flex items-center py-1 px-2 hover:bg-muted cursor-pointer"
              style={{ paddingLeft }}
              onClick={() => toggleExpand(node.path)}
            >
              {isExpanded ? 
                <ChevronDown className="h-4 w-4 mr-1" /> : 
                <ChevronRight className="h-4 w-4 mr-1" />
              }
              <Folder className="h-4 w-4 mr-2 text-blue-500" />
              <span className="truncate">{node.name}</span>
            </div>
            {isExpanded && node.children && (
              <div>{renderFileTree(node.children, depth + 1)}</div>
            )}
          </div>
        )
      } else {
        return (
          <div 
            key={node.path}
            className="flex items-center py-1 px-2 hover:bg-muted cursor-pointer"
            style={{ paddingLeft: `${paddingLeft}`}}
            onClick={() => onFileSelect(repoName, node.path)}
          >
            <div className="w-4 mr-1"></div> {/* Spacer to align with folders */}
            {renderFileIcon(node.name)}
            <span className="ml-2 truncate">{node.name}</span>
          </div>
        )
      }
    })
  }

  const processedStructure = processFileStructure(fileStructure)

  return (
    <div className="h-full overflow-auto p-2">
      <div className="font-semibold mb-2 px-2 flex items-center">
        <Folder className="h-5 w-5 mr-2 text-blue-500" />
        <span className="truncate">{repoName || "Repository Explorer"}</span>
      </div>
      
      {processedStructure.length > 0 ? (
        <div className="text-sm">
          {renderFileTree(processedStructure)}
        </div>
      ) : (
        <div className="text-sm text-muted-foreground p-2">
          {repoName ? "No files to display" : "Search for a repository to begin"}
        </div>
      )}
    </div>
  )
}

