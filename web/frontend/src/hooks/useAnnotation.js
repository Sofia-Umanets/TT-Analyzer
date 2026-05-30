import { useState, useCallback, useEffect } from 'react'
import {
  getAnnotation, saveAnnotation as saveAnnotationApi,
  addStroke as addStrokeApi, updateStroke as updateStrokeApi,
  deleteStroke as deleteStrokeApi, importAutoAnnotation,
} from '../api/client'

export default function useAnnotation(videoId) {
  const [annotation, setAnnotation] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!videoId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getAnnotation(videoId)
      setAnnotation(data)
    } catch (e) {
      if (e.response?.status === 404) {
        setAnnotation(null) // Нет разметки — это нормально
      } else {
        console.error('Ошибка загрузки разметки:', e)
        setError(e.message)
      }
    } finally {
      setLoading(false)
    }
  }, [videoId])

  useEffect(() => { load() }, [load])

  const save = useCallback(async () => {
    if (!annotation || !videoId) return
    try {
      await saveAnnotationApi(videoId, annotation)
    } catch (e) {
      console.error('Ошибка сохранения:', e)
      throw e
    }
  }, [videoId, annotation])

  const addStroke = useCallback(async (stroke) => {
    try {
      const created = await addStrokeApi(videoId, stroke)
      await load()
      return created
    } catch (e) {
      console.error('Ошибка добавления удара:', e)
      throw e
    }
  }, [videoId, load])

  const updateStroke = useCallback(async (strokeId, update) => {
    try {
      await updateStrokeApi(videoId, strokeId, update)
      await load()
    } catch (e) {
      console.error('Ошибка обновления удара:', e)
      throw e
    }
  }, [videoId, load])

  const removeStroke = useCallback(async (strokeId) => {
    try {
      await deleteStrokeApi(videoId, strokeId)
      await load()
    } catch (e) {
      console.error('Ошибка удаления удара:', e)
      throw e
    }
  }, [videoId, load])

  const importAuto = useCallback(async () => {
    try {
      await importAutoAnnotation(videoId)
      await load()
    } catch (e) {
      console.error('Ошибка импорта авто-разметки:', e)
      throw e
    }
  }, [videoId, load])

  return { annotation, loading, error, load, save, addStroke, updateStroke, removeStroke, importAuto }
}