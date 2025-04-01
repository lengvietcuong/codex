"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { GripVertical } from "lucide-react"

interface ResizableLayoutProps {
  leftPanel: React.ReactNode
  rightPanel: React.ReactNode
  defaultLeftWidth?: number
  minLeftWidth?: number
  maxLeftWidth?: number
}

export function ResizableLayout({
  leftPanel,
  rightPanel,
  defaultLeftWidth = 50,
  minLeftWidth = 30,
  maxLeftWidth = 70,
}: ResizableLayoutProps) {
  const [leftWidth, setLeftWidth] = useState(defaultLeftWidth)
  const [isResizing, setIsResizing] = useState(false)
  const resizeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return

      const windowWidth = window.innerWidth
      const newWidth = (e.clientX / windowWidth) * 100

      if (newWidth >= minLeftWidth && newWidth <= maxLeftWidth) {
        setLeftWidth(newWidth)
      }
    }

    const handleMouseUp = () => {
      setIsResizing(false)
    }

    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove)
      document.addEventListener("mouseup", handleMouseUp)
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isResizing, minLeftWidth, maxLeftWidth])

  return (
    <div className="flex h-screen w-full">
      {/* Left panel */}
      <div className="h-screen" style={{ width: `${leftWidth}%` }}>
        {leftPanel}
      </div>

      {/* Resize handle */}
      <div
        ref={resizeRef}
        className="w-2 bg-gray-100 hover:bg-gray-200 cursor-col-resize flex items-center justify-center"
        onMouseDown={() => setIsResizing(true)}
      >
        <GripVertical className="h-6 w-6 text-gray-400" />
      </div>

      {/* Right panel */}
      <div className="h-screen" style={{ width: `${100 - leftWidth - 0.5}%` }}>
        {rightPanel}
      </div>
    </div>
  )
}

