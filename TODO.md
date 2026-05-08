# TODO — 未实现功能清单

> 当前状态：真实人脸检测/识别/合照链路已接入 InsightFace（SCRFD + ArcFace）；`script/face_import.py` 已支持批量导入图片人脸库，`script/run_face_detection.py` 已支持本机摄像头实时调试；情绪分析与活体检测仍为占位实现

---

## 一、后端 AI 能力（核心缺口）

| # | 文件 | 问题 | 详情 |
|---|------|------|------|
| 1 | 人脸检测模型 | ✅ InsightFace SCRFD-10GF 已接入 | `face_pipeline.py` 通过 InsightFace buffalo_l 包加载 |
| 2 | `face_service.py:21-23` | ✅ `build_face_feature_from_path` 已改为 ArcFace 512 维真实特征 | InsightFace buffalo_l + ArcFace w600k_r50 |
| 3 | `face_service.py:26-32` | ✅ `match_student` 已改为余弦相似度 1:N 内存比对 | 启动时加载全量特征到内存 dict，<1ms 完成比对 |
| 4 | `face_service.py:35-46` | ✅ `simulate_group_matches` → `recognize_group` 真实多人脸检测+1:N比对 | InsightFace SCRFD 检测多人脸 → ArcFace 1:N 比对 |
| 4a | `group.py:42` | ✅ 合照识别的图片路径已传入 `recognize_group` | `str(destination)` 传入，真实读取图像内容 |
| 4b | 准确率 | ⚠️ 准确率需实测验证 | ArcFace 理论上 ≥95%，需真实数据验证 |
| 4c | `script/face_import.py` | ✅ 图片人脸库批量导入脚本已实现 | 递归扫描 `data/`，批量写入 `Student` / `FaceFeature` / `uploads/students` |
| 4d | `script/run_face_detection.py` | ✅ 本机实时调试脚本已实现 | 支持摄像头实时识别和 `--probe` 单图调试，显示人脸框、关键点、学号、分数 |
| 5 | `emotion_service.py:14-16` | ❌ `analyze_emotion` 用 SHA256 假分类 | 应接入 DeepFace 或真实情绪分类模型 |
| 6 | `liveness_service.py:1-6` | ❌ 永远返回 `{"implemented": False}` | 应接入 CDCN / Silent-Face 纹理活体检测 |
| 7 | `attendance.py:50` | ❌ `is_live` 字段恒为 `False` | 活体检测占位导致此字段永远假值 |
| 8 | `attendance.py:23-25` | ❌ `/action-challenge` 接口返回占位 | 动作活体（眨眼/张嘴）未实现 |

## 二、系统安全

| # | 功能 | 当前状态 |
|---|------|---------|
| 9 | 抗照片攻击（检测打印照片/屏幕翻拍） | ❌ 未实现 |
| 10 | 抗视频攻击（检测视频重放） | ❌ 未实现 |
| 11 | 教师/学生细粒度权限区分 | ❌ `require_teacher` 已定义（`dependencies.py:34`），但零个路由文件导入使用；所有路由仅用 `get_current_user`，任意登录用户可访问全部数据；前端 `router/index.js` 无角色守卫 |

## 三、后端接口缺失

| # | 接口 | 问题 |
|---|------|------|
| 12 | `GET /attendance/records` | ❌ 缺少 `date_from` / `date_to` 按日期筛选参数 |
| 13 | `GET /attendance/export` | ❌ 缺少按日期筛选参数 |

> API 文档 (`technical-api-document.md`) 描述了这两个参数，但实际代码未实现。

## 四、前端缺失

| # | 页面/组件 | 问题 |
|---|----------|------|
| 14 | `FaceMeshDetector.vue` | ❌ 纯占位组件，无真实人脸检测/活体动作检测 |
| 15 | `CameraCapture.vue:12` | ❌ "模拟自动抓拍提示" 按钮，无真实自动捕捉逻辑 |
| 16 | `Attendance.vue:49-59` | ❌ 考勤记录查询缺少按日期筛选 |
| 17 | `EmotionChart.vue:40` | ❌ 仅有柱状图，缺折线图（课程要求统计报表含折线图） |
| 18 | `Statistics.vue` | ❌ 活动频次统计仅图表展示，无独立统计表格 |

## 五、前端需求对照（课程评分标准详细排查）

以下是按课程评分标准逐项排查的结果，标注实际得分：

### 前端（12分）

| 评分项 | 分值 | 状态 | 备注 |
|--------|------|------|------|
| 摄像头调用正常、人脸采集流畅 | 3 | ✅ 3 | `CameraCapture.vue` getUserMedia + canvas 截帧 |
| 支持手动/自动捕捉并显示采集状态 | 3 | ⚠️ 2 | 手动✅，自动仅占位按钮 |
| 能实时渲染后端返回的学生信息 | 3 | ✅ 3 | `el-descriptions` 展示完整 |
| 支持筛选查询考勤记录 | 3 | ⚠️ 2 | 学号+姓名✅，缺按日期筛选 |
| **前端小计** | **12** | **10** | |

### 后端（13分）

| 评分项 | 分值 | 状态 | 备注 |
|--------|------|------|------|
| 活体检测正常，可抵御照片、视频欺骗 | 10 | ❌ 0 | `liveness_service.py` 占位，完全未实现 |
| 班级人脸库可批量导入、单个添加/删除/修改 | 2 | ✅ 2 | 单个接口完整；`POST /students/batch` 批量导入学生基本信息，`script/face_import.py` 批量导入图片人脸库 |
| 记录考勤数据并支持Excel格式导出 | 1 | ✅ 1 | `openpyxl` 生成 `.xlsx`，`StreamingResponse` 返回 |
| **后端小计** | **13** | **3** | 活体检测 10 分全丢 |

### 合照识别（9分）

| 评分项 | 分值 | 状态 | 备注 |
|--------|------|------|------|
| 照片人脸检测识别（合照检测+批量识别）| 3 | ✅ 3 | SCRFD + ArcFace 1:N 真实比对 |
| 识别准确率≥85%，处理10-50人合照 | 3 | ⚠️ 2 | ArcFace 理论≥95%，需实测验证 |
| 自动记录活动参与次数 | 2 | ✅ 2 | `activity_participant` 表统计 |
| 生成统计报表（统计数字/表格/柱状图/折线图）| 1 | ⚠️ 0.5 | 后端接口 ✅，前端仅柱状图；缺折线图、缺独立统计表格 |
| **合照小计** | **9** | **7.5** | |

### 情绪分析（8分）

| 评分项 | 分值 | 状态 | 备注 |
|--------|------|------|------|
| 考勤/合照中同步提取面部特征 | 2 | ⚠️ 1 | 已同步提取关键点与 ArcFace embedding，但情绪模块未使用真实表情特征 |
| 完成情绪分类 | 3 | ❌ 0 | `SHA256 % 7` 假分类 |
| 记录完整情绪数据 | 2 | ✅ 2 | `Attendance.emotion` 字段写入 |
| 前端查看统计结果 | 1 | ✅ 1 | `Statistics.vue` + `EmotionChart.vue` |
| **情绪小计** | **8** | **4** | 真实情绪分类缺失 |

### 系统安全（18分）

| 评分项 | 分值 | 状态 | 备注 |
|--------|------|------|------|
| 活体检测抗照片伪造 | 7 | ❌ 0 | 未实现 |
| 活体检测抗视频伪造 | 8 | ❌ 0 | 未实现 |
| 权限区分（教师/学生） | 3 | ❌ 0 | `require_teacher` 已定义但零使用；前端无角色路由；无学生数据隔离 |
| **安全小计** | **18** | **0** | |

---

## 六、神经网络架构与数据工程

| # | 模块 | 状态 |
|---|------|------|
| 19 | 端到端模型管线设计（SCRFD → ArcFace → 余弦比对） | ✅ `face_pipeline.py` 实现 | InsightFace buffalo_l：SCRFD-10GF + 2d106det + ArcFace w600k_r50 |
| 20 | `script/` 数据增强脚本（albumentations） | ⚠️ 已有 `download_models.py`，缺增强 | 模型下载脚本已创建 |
| 21 | `build_face_feature_from_path` 写入假特征到 `face_feature` 表 | ✅ 已改为 base64 编码的真实 512 维特征向量 | 启动时自动加载到内存 dict |

---

## 总分估算

| 模块 | 满分 | 预估得分 | 缺口 |
|------|------|---------|------|
| 架构 (10) | 10 | ~8 | 分层清晰，API 规范 |
| 前端考勤 (12) | 12 | ~10 | 缺自动捕捉、日期筛选 |
| 后端考勤 (13) | 13 | ~3 | 活体检测 0 分 |
| 合照识别 (9) | 9 | ~7 | 准确率需实测验证、前端报表缺折线图 |
| 情绪分析 (8) | 8 | ~4 | 假分类，未接入真实表情特征 |
| 系统安全 (18) | 18 | 0 | 全部未实现 |
| 实验报告 (30) | 30 | ~20 | 取决于文档完善度 |
| **合计** | **100** | **~52** | | |
