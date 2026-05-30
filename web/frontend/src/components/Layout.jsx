import React, { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { getHealth } from '../api/client'

export default function Layout({ children }) {
  const location = useLocation()
  const [health, setHealth] = useState(null)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null))
  }, [])

  const nav = [
    { path: '/', label: 'Главная' },
    { path: '/videos', label: 'Видео' },
    { path: '/compare', label: 'Сравнение' },
    { path: '/models', label: 'Модели' },
  ]

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="bg-gray-800 border-b border-gray-700 sticky top-0 z-40">
        <div className="px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link to="/" className="text-xl font-bold">🏓 TT Analyzer</Link>
            <nav className="flex gap-2">
              {nav.map(({ path, label }) => (
                <Link
                  key={path}
                  to={path}
                  className={`px-4 py-2 rounded text-base ${
                    location.pathname === path
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  {label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            {health ? (
              <>
                <span className={`w-2.5 h-2.5 rounded-full ${health.models_loaded ? 'bg-green-400' : 'bg-yellow-400'}`} />
                <span className="text-gray-400">
                  Модели: {Object.values(health.models_available || {}).filter(Boolean).length}/{Object.keys(health.models_available || {}).length}
                </span>
              </>
            ) : (
              <>
                <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
                <span className="text-gray-400">Бэкенд недоступен</span>
              </>
            )}
          </div>
        </div>
      </header>
      <main className="px-6 py-6">{children}</main>
    </div>
  )
}