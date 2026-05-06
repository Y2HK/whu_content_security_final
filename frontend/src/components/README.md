# components 模块说明

## 职责
可复用组件，封装特定功能，供多个页面调用。

## 文件说明

| 文件 | 职责 | 输入/输出 |
|------|------|-----------|
| `CameraCapture.vue` | WebRTC 摄像头封装 | 输出：视频流/拍照 Blob |
| `FaceMeshDetector.vue` | MediaPipe 动作检测 | 输入：视频流；输出：动作验证结果/人脸框坐标 |
| `EmotionChart.vue` | ECharts 情绪统计图表 | 输入：情绪分布数据；输出：渲染柱状图/饼图 |

## 使用方式

```vue
<template>
  <CameraCapture ref="camera" @capture="onCapture" />
  <FaceMeshDetector :video="videoEl" @verified="onVerified" />
  <EmotionChart :data="emotionData" />
</template>
```
