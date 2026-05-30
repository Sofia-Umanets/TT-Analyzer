import React, { useState, useRef } from 'react'
import { uploadVideo } from '../api/client'

export default function UploadModal({ open, onClose, onUploaded }) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)
  const fileRef = useRef(null)

  if (!open) return null

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)
    setProgress(0)

    try {
      const result = await uploadVideo(file, setProgress)
      onUploaded?.(result)
      onClose()
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Ошибка загрузки')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-gray-800 rounded-lg p-6 w-96 max-w-[90vw]" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold mb-4">Загрузить видео</h2>

        <input
          ref={fileRef}
          type="file"
          accept="video/*"
          className="w-full mb-4 text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-blue-600 file:text-white file:cursor-pointer"
        />

        {uploading && (
          <div className="mb-4">
            <div className="w-full bg-gray-700 rounded h-2">
              <div
                className="bg-blue-500 h-2 rounded transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 mt-1">{progress}%</p>
          </div>
        )}

        {error && (
          <p className="text-red-400 text-sm mb-4">{error}</p>
        )}

        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded text-sm"
            disabled={uploading}
          >
            Отмена
          </button>
          <button
            onClick={handleUpload}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm"
            disabled={uploading}
          >
            {uploading ? 'Загрузка...' : 'Загрузить'}
          </button>
        </div>
      </div>
    </div>
  )
}