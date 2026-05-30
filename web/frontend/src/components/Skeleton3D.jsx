import React, { useState, useEffect, useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { getSkeleton } from '../api/client'

const BONE_COLOR = '#3b82f6'
const HIGHLIGHT_JOINTS = ['right_wrist', 'left_wrist', 'right_elbow', 'left_elbow']

function Joint({ position, isHighlight }) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[isHighlight ? 0.015 : 0.01, 16, 16]} />
      <meshStandardMaterial color={isHighlight ? '#ef4444' : '#f59e0b'} />
    </mesh>
  )
}

function Bone({ start, end }) {
  const mid = [
    (start[0] + end[0]) / 2,
    (start[1] + end[1]) / 2,
    (start[2] + end[2]) / 2,
  ]
  const dx = end[0] - start[0], dy = end[1] - start[1], dz = end[2] - start[2]
  const length = Math.sqrt(dx * dx + dy * dy + dz * dz)
  const ref = useRef()

  useEffect(() => { ref.current?.lookAt(end[0], end[1], end[2]) }, [end])

  return (
    <mesh position={mid} ref={ref}>
      <cylinderGeometry args={[0.004, 0.004, length, 8]} />
      <meshStandardMaterial color={BONE_COLOR} />
    </mesh>
  )
}

function SkeletonModel({ landmarks, connections }) {
  if (!landmarks) return null

  const toPos = (name) => {
    const lm = landmarks[name]
    if (!lm) return [0, 0, 0]
    return [lm[0] - 0.5, -(lm[1] - 0.5), -(lm[2] || 0)]
  }

  return (
    <group>
      {Object.keys(landmarks).map(name => (
        <Joint
          key={name}
          position={toPos(name)}
          name={name}
          isHighlight={HIGHLIGHT_JOINTS.includes(name)}
        />
      ))}
      {connections?.map(([a, b], i) => {
        if (!landmarks[a] || !landmarks[b]) return null
        return <Bone key={i} start={toPos(a)} end={toPos(b)} />
      })}
    </group>
  )
}

export default function Skeleton3D({ videoId, frame, videoRef, fps }) {
  const [skeleton, setSkeleton] = useState(null)
  const [loading, setLoading]   = useState(false)
  const cacheRef      = useRef(new Map())   // frame → skeleton data
  const rvcHandleRef  = useRef(null)
  const lastFrameRef  = useRef(-1)

  const fetchFrame = (f) => {
    if (!videoId || f == null || f < 0) return
    // Попадание в кэш — мгновенно
    if (cacheRef.current.has(f)) {
      setSkeleton(cacheRef.current.get(f))
      return
    }
    setLoading(true)
    getSkeleton(videoId, f)
      .then(data => {
        cacheRef.current.set(f, data)
        // Ограничиваем размер кэша
        if (cacheRef.current.size > 60) {
          const firstKey = cacheRef.current.keys().next().value
          cacheRef.current.delete(firstKey)
        }
        if (lastFrameRef.current === f) setSkeleton(data)
      })
      .catch(() => { if (lastFrameRef.current === f) setSkeleton(null) })
      .finally(() => setLoading(false))
  }

  // requestVideoFrameCallback если передан videoRef + fps
  useEffect(() => {
    const video = videoRef?.current
    if (!video || !fps) return

    const onFrame = (_now, metadata) => {
      const f = fps > 0 ? Math.round(metadata.mediaTime * fps) : 0
      if (f !== lastFrameRef.current) {
        lastFrameRef.current = f
        fetchFrame(f)
      }
      rvcHandleRef.current = video.requestVideoFrameCallback(onFrame)
    }

    if ('requestVideoFrameCallback' in HTMLVideoElement.prototype) {
      rvcHandleRef.current = video.requestVideoFrameCallback(onFrame)
    }

    return () => {
      if (rvcHandleRef.current != null && 'cancelVideoFrameCallback' in HTMLVideoElement.prototype) {
        video.cancelVideoFrameCallback(rvcHandleRef.current)
        rvcHandleRef.current = null
      }
    }
  }, [videoRef, fps, videoId])

  // Fallback: обновление по пропу frame (когда videoRef не передан)
  useEffect(() => {
    if (videoRef?.current && fps) return  // rVFC уже работает
    if (frame === lastFrameRef.current) return
    lastFrameRef.current = frame
    fetchFrame(frame)
  }, [videoId, frame])

  // Сброс кэша при смене видео
  useEffect(() => {
    cacheRef.current.clear()
    lastFrameRef.current = -1
    setSkeleton(null)
  }, [videoId])

  if (loading && !skeleton) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
        Загрузка скелета...
      </div>
    )
  }

  if (!skeleton?.detected) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
        Поза не найдена (кадр {lastFrameRef.current})
      </div>
    )
  }

  return (
    <div className="h-64 bg-gray-900 rounded">
      <Canvas camera={{ position: [0, 0, 1.5], fov: 50 }}>
        <ambientLight intensity={0.5} />
        <pointLight position={[2, 2, 2]} intensity={1} />
        <SkeletonModel landmarks={skeleton.landmarks} connections={skeleton.connections} />
        <OrbitControls enablePan enableZoom />
        <gridHelper args={[2, 20, '#333', '#222']} />
      </Canvas>
    </div>
  )
}
