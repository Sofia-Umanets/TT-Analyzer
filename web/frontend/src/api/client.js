import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 300000 })

export const getVideos = () => api.get('/videos').then(r => r.data)
export const getVideo = (id) => api.get(`/videos/${id}`).then(r => r.data)
export const uploadVideo = (file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/videos', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  }).then(r => r.data)
}
export const deleteVideo = (id) => api.delete(`/videos/${id}`).then(r => r.data)

export const getAnnotation = (videoId) => api.get(`/annotations/${videoId}`).then(r => r.data)
export const getErrorTypes = () => api.get('/annotations/types/list').then(r => r.data)
export const saveAnnotation = (videoId, data) => api.put(`/annotations/${videoId}`, data).then(r => r.data)
export const addStroke = (videoId, stroke) => api.post(`/annotations/${videoId}/strokes`, stroke).then(r => r.data)
export const updateStroke = (videoId, strokeId, update) => api.patch(`/annotations/${videoId}/strokes/${strokeId}`, update).then(r => r.data)
export const deleteStroke = (videoId, strokeId) => api.delete(`/annotations/${videoId}/strokes/${strokeId}`).then(r => r.data)
export const importAutoAnnotation = (videoId) => api.post(`/annotations/${videoId}/import-auto`).then(r => r.data)
export const exportAnnotation = (videoId) => `/api/annotations/${videoId}/export`

export const runAnalysis = (videoId) => api.post(`/analysis/${videoId}/run`).then(r => r.data)
export const getAnalysisProgress = (videoId) => api.get(`/analysis/${videoId}/progress`).then(r => r.data)
export const getAnalysisResult = (videoId) => api.get(`/analysis/${videoId}/result`).then(r => r.data)
export const getPhases = (videoId) => api.get(`/analysis/${videoId}/phases`).then(r => r.data)

export const getFeatures = (videoId, start, end, step = 1) =>
  api.get(`/viz/${videoId}/features`, { params: { start, end, step } }).then(r => r.data)
export const getSkeleton = (videoId, frame) => api.get(`/viz/${videoId}/skeleton/${frame}`).then(r => r.data)
export const getStrokeAttention = (videoId, strokeId) => api.get(`/viz/${videoId}/stroke/${strokeId}/attention`).then(r => r.data)
export const getStrokeFeatures = (videoId, strokeId) => api.get(`/viz/${videoId}/stroke/${strokeId}/features`).then(r => r.data)

export const getHealth = () => api.get('/health').then(r => r.data)

export const runTraining = (model) => api.post(`/training/${model}/run`).then(r => r.data)
export const getTrainingProgress = (model) => api.get(`/training/${model}/progress`).then(r => r.data)
export const getTrainingStats = () => api.get('/training/stats').then(r => r.data)

export const startFeatureExtraction = (force = false) =>
  api.post('/features/extract', null, { params: { force } }).then(r => r.data)
export const getFeatureExtractionProgress = () =>
  api.get('/features/extract/progress').then(r => r.data)

export const getFeatureImportance = () =>
  api.get('/training/feature_importance').then(r => r.data)
export const getAllLandmarks = (videoId) =>
  api.get(`/viz/${videoId}/landmarks`).then(r => r.data)

export const compareStrokes = (strokes, normalize = false) =>
  api.post('/compare/', { strokes, normalize }).then(r => r.data)