import React from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

const COLORS = ['#3b82f6', '#ef4444', '#22c55e', '#eab308', '#a855f7', '#f97316']

export default function FeatureChart({
  data,               // [{ frame, features: { name: value } }]
  featureNames,       // ['right_wrist_speed', ...]
  contactFrame,
  title,
  highlightedFeature, // имя признака для акцента (толще + зелёный)
}) {
  if (!data || data.length === 0) return null

  const chartData = data.map(d => {
    const point = { frame: d.frame }
    featureNames.forEach(name => { point[name] = d.features?.[name] ?? 0 })
    return point
  })

  return (
    <div className="bg-gray-800 rounded-lg p-3">
      {title && <h4 className="text-sm text-gray-300 mb-2 font-medium">{title}</h4>}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mb-2">
        {featureNames.map((name, i) => (
          <span key={name} className="flex items-center gap-1 text-xs">
            <span
              className="inline-block w-4 h-0.5"
              style={{ backgroundColor: name === highlightedFeature ? '#22c55e' : COLORS[i % COLORS.length] }}
            />
            <span className={name === highlightedFeature ? 'text-green-400 font-medium' : 'text-gray-400'}>
              {name.replace(/_/g, ' ')}
            </span>
          </span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chartData}>
          <XAxis dataKey="frame" tick={{ fontSize: 11, fill: '#9ca3af' }} />
          <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} />
          <Tooltip
            contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
            labelStyle={{ color: '#9ca3af' }}
          />
          {contactFrame != null && (
            <ReferenceLine x={contactFrame} stroke="#fbbf24" strokeDasharray="4 2" label={{ value: 'C', fill: '#fbbf24', fontSize: 11 }} />
          )}
          {featureNames.map((name, i) => (
            <Line
              key={name}
              type="monotone"
              dataKey={name}
              stroke={name === highlightedFeature ? '#22c55e' : COLORS[i % COLORS.length]}
              strokeWidth={name === highlightedFeature ? 2.5 : 1.5}
              dot={false}
              name={name.replace(/_/g, ' ')}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
