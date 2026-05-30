import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getVideos, getHealth } from '../api/client'

export default function DashboardPage() {
  const [videos, setVideos] = useState([])
  const [health, setHealth] = useState(null)

  useEffect(() => {
    getVideos().then(d => setVideos(d.videos)).catch(() => {})
    getHealth().then(setHealth).catch(() => {})
  }, [])

  const stats = {
    total: videos.length,
    annotated: videos.filter(v => v.annotation_status !== 'none').length,
    analyzed: videos.filter(v => v.has_analysis).length,
  }

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold">Панель управления</h1>

      <div className="grid grid-cols-3 gap-6">
        <div className="bg-gray-800 rounded-lg p-6 text-center">
          <div className="text-4xl font-bold">{stats.total}</div>
          <div className="text-base text-gray-400 mt-2">Всего видео</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-6 text-center">
          <div className="text-4xl font-bold text-blue-400">{stats.annotated}</div>
          <div className="text-base text-gray-400 mt-2">Размечено</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-6 text-center">
          <div className="text-4xl font-bold text-purple-400">{stats.analyzed}</div>
          <div className="text-base text-gray-400 mt-2">Проанализировано</div>
        </div>
      </div>

      {health && (
        <div className="bg-gray-800 rounded-lg p-5">
          <h2 className="text-lg font-bold mb-3">Модели</h2>
          <div className="grid grid-cols-3 gap-4">
            {Object.entries(health.models_available || {}).map(([name, loaded]) => (
              <div key={name} className="flex items-center gap-3">
                <span className={`w-3 h-3 rounded-full ${loaded ? 'bg-green-400' : 'bg-red-400'}`} />
                <span className="text-base text-gray-300">{name.replace(/_/g, ' ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-gray-800 rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Последние видео</h2>
          <Link to="/videos" className="text-sm text-blue-400 hover:text-blue-300">Все →</Link>
        </div>
        <div className="space-y-2">
          {videos.slice(0, 10).map(v => (
            <div key={v.id} className="flex items-center justify-between bg-gray-700/50 rounded p-3">
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-base truncate">{v.filename}</span>
                <span className="text-sm text-gray-500">{v.duration?.toFixed(1)}с</span>
              </div>
              <div className="flex gap-3">
                <Link to={`/annotate/${v.id}`} className="text-sm text-blue-400 hover:text-blue-300">Разметка</Link>
                <Link to={`/analysis/${v.id}`} className="text-sm text-purple-400 hover:text-purple-300">Анализ</Link>
              </div>
            </div>
          ))}
          {videos.length === 0 && (
            <p className="text-gray-500 text-center py-6 text-base">
              <Link to="/videos" className="text-blue-400">Загрузите первое видео</Link>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}