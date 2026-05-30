import React from 'react'
import {
  ComposedChart, Line, Area,
  XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'

const FEATURE_NAMES_RU = {
  right_wrist_speed:              'Скорость правого запястья',
  left_wrist_speed:               'Скорость левого запястья',
  right_elbow_speed:              'Скорость правого локтя',
  left_elbow_speed:               'Скорость левого локтя',
  right_wrist_accel:              'Ускорение правого запястья',
  left_wrist_accel:               'Ускорение левого запястья',
  right_elbow_angular_vel:        'Угловая скорость локтя (пр.)',
  right_shoulder_angular_vel:     'Угловая скорость плеча (пр.)',
  right_elbow_angle:              'Угол правого локтя',
  left_elbow_angle:               'Угол левого локтя',
  right_shoulder_angle:           'Угол правого плеча',
  left_shoulder_angle:            'Угол левого плеча',
  right_knee_angle:               'Угол правого колена',
  left_knee_angle:                'Угол левого колена',
  right_hip_angle:                'Угол правого бедра',
  left_hip_angle:                 'Угол левого бедра',
  shoulder_hip_rotation:          'Вращение плечи–бёдра',
  torso_forward_tilt:             'Наклон корпуса вперёд',
  torso_side_tilt:                'Боковой наклон корпуса',
  shoulder_height_diff:           'Разность высоты плеч',
  stance_width:                   'Ширина стойки',
  right_wrist_dist_body:          'Расстояние запястья от тела',
  right_elbow_height_vs_shoulder: 'Высота локтя от плеча',
  right_wrist_rel_x:              'Запястье: позиция X',
  right_wrist_rel_y:              'Запястье: позиция Y (высота)',
  right_wrist_rel_z:              'Запястье: позиция Z (глубина)',
  left_wrist_rel_x:               'Лев. запястье: позиция X',
  right_elbow_rel_x:              'Локоть: позиция X',
  right_elbow_rel_y:              'Локоть: позиция Y (высота)',
  right_wrist_dir_x:              'Направление запястья X',
  right_wrist_dir_y:              'Направление запястья Y',
  right_wrist_dir_z:              'Направление запястья Z',
  right_wrist_from_neutral:       'Отклонение запястья от нейтрали',
  left_wrist_from_neutral:        'Отклонение лев. запястья',
  elbow_angle_diff:               'Разница углов локтей',
  shoulder_angle_diff:            'Разница углов плеч',
  knee_angle_diff:                'Разница углов колен',
  wrist_distance:                 'Расстояние между запястьями',
  right_wrist_height_vs_shoulder: 'Высота прав. запястья над плечом',
  left_wrist_height_vs_shoulder:  'Высота лев. запястья над плечом',
}

export default function ErrorSaliencyChart({ strokeFrames, saliency, contactFrame, errorName }) {
  if (!saliency || !strokeFrames?.length) return null

  const { top_features, frame_gradients } = saliency
  if (!top_features?.length || !frame_gradients) return null

  const featuresToShow = top_features.slice(0, 4)

  return (
    <div className="bg-gray-800 rounded-lg p-3 space-y-3">
      <div>
        <h4 className="text-sm font-semibold text-red-400 mb-0.5">
          Почему модель нашла ошибку: «{errorName}»
        </h4>
        <p className="text-xs text-gray-500 leading-snug">
          Синяя линия — значение параметра по кадрам.&nbsp;
          Оранжевая заливка — насколько модель смотрела на этот параметр в каждый момент
          (чем ярче — тем важнее для этого решения).&nbsp;
          Пунктир <span className="text-amber-400">жёлтый</span> — момент удара,&nbsp;
          <span className="text-orange-400">оранжевый</span> — пик внимания.
        </p>
      </div>

      {featuresToShow.map(featureName => {
        const gradients = frame_gradients[featureName]
        if (!gradients) return null

        // Merge feature values with gradient into one data array
        const data = strokeFrames.map((f, i) => ({
          frame: f.frame,
          value: f.features?.[featureName] ?? null,
          attention: gradients[i] ?? 0,
        }))

        // Frame with highest gradient
        let peakFrame = null
        let peakVal = -1
        gradients.forEach((v, i) => {
          if (v > peakVal) { peakVal = v; peakFrame = strokeFrames[i]?.frame }
        })

        const label = FEATURE_NAMES_RU[featureName] ?? featureName.replace(/_/g, ' ')

        return (
          <div key={featureName} className="bg-gray-750 rounded p-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-gray-200">{label}</span>
              {peakFrame != null && (
                <span className="text-xs text-orange-400">
                  Пик внимания: кадр {peakFrame}
                </span>
              )}
            </div>
            <ResponsiveContainer width="100%" height={120}>
              <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <XAxis
                  dataKey="frame"
                  tick={{ fontSize: 11, fill: '#9ca3af' }}
                  label={{ value: 'кадр', position: 'insideBottomRight', offset: -4, fontSize: 11, fill: '#6b7280' }}
                />
                {/* Left axis for feature value */}
                <YAxis yAxisId="val" tick={{ fontSize: 11, fill: '#9ca3af' }} width={36} />
                {/* Right axis for attention (hidden ticks, 0..1) */}
                <YAxis yAxisId="attn" orientation="right" domain={[0, 1]} hide />

                <Tooltip
                  contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 12 }}
                  labelFormatter={f => `кадр ${f}`}
                  formatter={(v, name) => {
                    if (name === 'attention') return [`${(v * 100).toFixed(0)}%`, 'Внимание модели']
                    return [v?.toFixed(3) ?? '—', 'Значение']
                  }}
                />

                {/* Attention as orange fill behind the line */}
                <Area
                  yAxisId="attn"
                  type="monotone"
                  dataKey="attention"
                  fill="#f97316"
                  fillOpacity={0.22}
                  stroke="#f97316"
                  strokeOpacity={0.35}
                  strokeWidth={1}
                  dot={false}
                  activeDot={false}
                  name="attention"
                  legendType="none"
                />

                {/* Feature value as blue line */}
                <Line
                  yAxisId="val"
                  type="monotone"
                  dataKey="value"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  name="value"
                  legendType="none"
                  connectNulls
                />

                {/* Contact frame — yellow dashed */}
                {contactFrame != null && (
                  <ReferenceLine
                    yAxisId="val"
                    x={contactFrame}
                    stroke="#fbbf24"
                    strokeDasharray="4 2"
                    strokeWidth={1.5}
                    label={{ value: 'удар', position: 'insideTopRight', fontSize: 9, fill: '#fbbf24' }}
                  />
                )}

                {/* Peak attention frame — orange dashed (only if different from contact) */}
                {peakFrame != null && peakFrame !== contactFrame && (
                  <ReferenceLine
                    yAxisId="val"
                    x={peakFrame}
                    stroke="#f97316"
                    strokeDasharray="3 2"
                    strokeWidth={1.5}
                    label={{ value: '▲', position: 'insideTopLeft', fontSize: 10, fill: '#f97316' }}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )
      })}
    </div>
  )
}
