'use client'

import * as React from 'react'
import { useState, useEffect, useRef } from 'react'

interface VerticalResizableProps {
  topPanel: React.ReactNode
  bottomPanel: React.ReactNode
  defaultTopHeight?: number
  minTopHeight?: number
  minBottomHeight?: number
}

export function VerticalResizable({
  topPanel,
  bottomPanel,
  defaultTopHeight = 50,
  minTopHeight = 10,
  minBottomHeight = 10,
}: VerticalResizableProps) {
  const [topHeight, setTopHeight] = useState<number>(defaultTopHeight)
  const containerRef = useRef<HTMLDivElement>(null)
  const isDragging = useRef<boolean>(false)
  const startY = useRef<number>(0)
  const startHeight = useRef<number>(0)

  const onMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    isDragging.current = true
    startY.current = e.clientY
    startHeight.current = topHeight
    document.body.style.cursor = 'ns-resize'
    document.body.style.userSelect = 'none'
  }

  const onMouseMove = (e: MouseEvent) => {
    if (!isDragging.current) return
    
    const containerHeight = containerRef.current?.clientHeight || 0
    const delta = e.clientY - startY.current
    const newHeight = startHeight.current + (delta / containerHeight) * 100
    
    const topHeightPercent = Math.max(minTopHeight, Math.min(100 - minBottomHeight, newHeight))
    setTopHeight(topHeightPercent)
  }

  const onMouseUp = () => {
    isDragging.current = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  useEffect(() => {
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
    
    return () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  return (
    <div ref={containerRef} className="flex flex-col h-full relative">
      <div style={{ height: `${topHeight}%` }} className="overflow-auto">
        {topPanel}
      </div>
      
      <div 
        className="cursor-ns-resize h-2 bg-gray-200 hover:bg-gray-300 active:bg-gray-400 w-full flex items-center justify-center"
        onMouseDown={onMouseDown}
      >
        <div className="w-8 h-1 bg-gray-400 rounded-full" />
      </div>
      
      <div style={{ height: `calc(${100 - topHeight}% - 0.5rem)` }} className="overflow-auto">
        {bottomPanel}
      </div>
    </div>
  )
}
