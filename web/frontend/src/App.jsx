import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import VideoListPage from './pages/VideoListPage'
import AnnotatePage from './pages/AnnotatePage'
import AnalysisPage from './pages/AnalysisPage'
import ModelsPage from './pages/ModelsPage'
import ComparePage from './pages/ComparePage'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/videos" element={<VideoListPage />} />
        <Route path="/annotate/:videoId" element={<AnnotatePage />} />
        <Route path="/analysis/:videoId" element={<AnalysisPage />} />
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}