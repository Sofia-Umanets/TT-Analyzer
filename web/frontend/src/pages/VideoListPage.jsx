import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { getVideos, deleteVideo } from '../api/client'
import UploadModal from '../components/UploadModal'

const ANN_LABELS = {
  none: { text: 'Нет', cls: 'text-gray-500' },
  auto: { text: 'Авто', cls: 'text-yellow-400' },
  manual: { text: 'Ручная', cls: 'text-green-400' },
}

export default function VideoListPage() {
  const [videos, setVideos] = useState([])
  const [showUpload, setShowUpload] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { setVideos((await getVideos()).videos) } catch {} finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleDelete = async (id, name) => {
    if (!confirm(`Удалить "${name}"?`)) return
    await deleteVideo(id)
    await load()
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Видео</h1>
        <button onClick={() => setShowUpload(true)} className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded text-base">
          + Загрузить
        </button>
      </div>

      {loading ? <p className="text-gray-400 text-center py-8 text-lg">Загрузка...</p> :
       videos.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-400 text-xl mb-4">Нет видео</p>
          <button onClick={() => setShowUpload(true)} className="bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded text-lg">
            Загрузить первое видео
          </button>
        </div>
      ) : (
        <div className="grid gap-3">
          {videos.map(v => {
            const ann = ANN_LABELS[v.annotation_status] || ANN_LABELS.none
            return (
              <div key={v.id} className="bg-gray-800 rounded-lg p-4 flex items-center gap-5">
                <div className="w-32 h-20 bg-gray-700 rounded overflow-hidden flex-shrink-0">
                  {v.thumbnail ? <img src={v.thumbnail} alt="" className="w-full h-full object-cover" /> :
                   <div className="w-full h-full flex items-center justify-center text-3xl text-gray-500">🎬</div>}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-base font-medium truncate">{v.filename}</div>
                  <div className="text-sm text-gray-400 mt-1 flex gap-4 flex-wrap">
                    <span>{v.duration?.toFixed(1)}с</span>
                    <span>{v.total_frames} кадров</span>
                    <span>{v.fps} fps</span>
                    {v.width > 0 && <span>{v.width}×{v.height}</span>}
                    {v.size_mb > 0 && <span>{v.size_mb} МБ</span>}
                  </div>
                  <div className="text-sm mt-1 flex gap-4">
                    <span>Разметка: <span className={ann.cls}>{ann.text}</span></span>
                    {v.has_analysis && <span className="text-purple-400">Анализ ✓</span>}
                  </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <Link to={`/annotate/${v.id}`} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm">Разметка</Link>
                  <Link to={`/analysis/${v.id}`} className="px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded text-sm">Анализ</Link>
                  <button onClick={() => handleDelete(v.id, v.filename)} className="px-4 py-2 bg-red-700 hover:bg-red-600 rounded text-sm">✕</button>
                </div>
              </div>
            )
          })}
        </div>
      )}
      <UploadModal open={showUpload} onClose={() => setShowUpload(false)} onUploaded={load} />
    </div>
  )
}