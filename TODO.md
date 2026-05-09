# TODO - 课程设计功能完成度核查

> 核查依据：`2026《内容安全实验课》课程设计要求及评分标准.docx`。
> 当前状态：`final` 已合并 `final_lzb` 的 InsightFace 合照/人脸识别链路，并保留原有 DeepFace 情绪分析、动作活体交互、教师/学生权限隔离与测试；已补充考勤日期筛选和统计折线图。主要短板集中在强制活体与抗照片/视频攻击、统计报表导出、报告材料收尾。

---

## 一、总体结论

| 模块 | 满分 | 预估得分 | 状态 | 主要缺口 |
|---|---:|---:|---|---|
| 架构要求 | 10 | 9 | 基本完成 | 文档可再补部署/算法说明细节 |
| 基础考勤 | 25 | 17-19 | 部分完成 | 自动捕捉、人脸库真实批量照片导入说明、强制活体不足 |
| 合照识别 | 9 | 7-8 | 基本完成 | 准确率和 10-50 人合照压力测试未形成证据 |
| 情绪分析 | 8 | 6-7 | 基本完成 | 合照情绪未精确绑定每张裁剪人脸，DeepFace 失败时会降级为演示结果 |
| 系统安全 | 18 | 5-6 | 明显不足 | 活体可跳过，后端不强制动作验证，抗照片/视频攻击未闭环 |
| 实验报告/源码 | 30 | 20-24 | 部分完成 | 缺正式课程设计报告和测试结果分析 |
| **合计** | **100** | **约 63-72** | 可运行但安全项拖分 | 优先补活体、防伪与报告 |

---

## 二、架构要求核查（10 分）

| 评分项 | 分值 | 状态 | 证据/说明 |
|---|---:|---|---|
| BS 分层架构清晰 | 3 | [完成] | `frontend/` + `backend/app/routers` + `backend/app/services` + `backend/app/db` 分层明确 |
| 前端适配主流浏览器，界面友好 | 3 | [基本完成] | Vue3 + Element Plus；摄像头依赖浏览器 `getUserMedia`，Chrome/Edge 可用 |
| 后端 API 规范，可实现核心交互 | 2 | [完成] | FastAPI 路由覆盖 auth/students/attendance/group/emotion |
| 数据库设计合理 | 2 | [完成] | `user`、`student`、`face_feature`、`attendance`、`activity`、`activity_participant` 表已建立关联 |

**待补事项**

| 优先级 | 文件/位置 | 问题 | 建议 |
|---|---|---|---|
| 中 | `docs/`、报告 | 架构、算法和部署说明分散 | 在正式报告中补系统架构图、数据库 ER 图、算法流程图 |

---

## 三、基础考勤功能核查（25 分）

### 3.1 前端（12 分）

| 评分项 | 分值 | 状态 | 证据/说明 |
|---|---:|---|---|
| 摄像头调用正常、人脸采集流畅 | 3 | [完成] | `CameraCapture.vue` 使用 `navigator.mediaDevices.getUserMedia`，支持拍照上传 |
| 支持手动/自动捕捉并显示采集状态 | 3 | [部分] | 手动拍照完成；`CameraCapture.vue` 的自动抓拍仍是“模拟自动抓拍提示”；`FaceMeshDetector.vue` 有动作验证后自动提交 |
| 实时渲染后端返回学生信息 | 3 | [完成] | `Attendance.vue` 展示姓名、学号、状态、情绪、置信度、时间、活体结果 |
| 支持考勤记录筛选查询 | 3 | [完成] | 前端支持学号、姓名、日期范围筛选；后端 `records/export` 支持 `date_from/date_to` |

### 3.2 后端（13 分）

| 评分项 | 分值 | 状态 | 证据/说明 |
|---|---:|---|---|
| 活体检测可抵御照片、视频欺骗 | 10 | [部分偏弱] | `FaceMeshDetector.vue` 有眨眼/张嘴动作验证，`liveness_service.py` 预留 custom/CDCN/Silent-Face 模型加载；但模型不存在时默认 `is_live=True`，且后端未强制必须带有效 challenge |
| 班级人脸库批量导入、单个增删改 | 2 | [完成] | `students.py` 支持 CRUD、CSV 批量导入、单人脸上传；`script/face_import.py` 支持图片人脸库批量导入 |
| 记录考勤数据并支持 Excel 导出 | 1 | [完成] | `attendance.py` 写入 `Attendance`，`/attendance/export` 用 `openpyxl` 导出 |

**待补事项**

| 优先级 | 文件/位置 | 问题 | 建议 |
|---|---|---|---|
| 高 | `backend/app/routers/attendance.py` | `/attendance/check` 不强制验证 `challenge_id`，直接图片上传仍可考勤 | 要求所有摄像头考勤必须先完成动作挑战；普通图片上传可改为教师调试入口或禁用 |
| 高 | `backend/app/services/liveness_service.py` | 无模型时默认通过，抗照片/视频攻击得分很低 | 提供可运行的 Silent-Face/CDCN 权重或实现稳定纹理/动作融合策略；无模型时应标记“不具备安全活体能力” |
| 高 | `frontend/src/components/CameraCapture.vue` | 自动抓拍只是提示，没有真正人脸稳定检测后自动拍照 | 接入 FaceMesh/MediaPipe 检测人脸框，满足稳定居中后自动截帧 |
| 已完成 | `backend/app/routers/attendance.py` | `records/export` 已支持 `date_from/date_to` | 查询和 Excel 导出共用日期范围筛选 |
| 已完成 | `frontend/src/views/Attendance.vue` | 筛选表单已加入日期范围 | 日期选择器会传 `date_from/date_to` 给后端 |

---

## 四、合照学生识别功能核查（9 分）

| 评分项 | 分值 | 状态 | 证据/说明 |
|---|---:|---|---|
| 前端上传合照 | 1 | [完成] | `GroupPhoto.vue` 支持活动名、日期、图片上传 |
| 后端检测并批量识别人脸 | 2 | [完成] | `group.py` 调用 `recognize_group`；`face_pipeline.py` 使用 InsightFace `buffalo_l` |
| 匹配人脸库并生成参与名单 | 3 | [完成] | `face_service.py` 使用 ArcFace 512 维特征和内存人脸库做 1:N 余弦匹配，返回学号、姓名、置信度、情绪 |
| 准确率大于等于 85%，处理 10-50 人合照 | 3 | [部分] | 模型链路具备能力，但缺真实测试集、准确率统计和多人合照压力测试记录 |
| 自动记录活动参与次数 | 2 | [完成] | `activity_participant` 记录参与学生；`/group/statistics` 统计次数 |
| 统计报表：数字、表格、柱状图等 | 1 | [基本完成] | `GroupPhoto.vue` 有活动表和名单表；`Statistics.vue` 有柱状图和折线图；缺统计报表导出 |

**待补事项**

| 优先级 | 文件/位置 | 问题 | 建议 |
|---|---|---|---|
| 高 | 测试数据/报告 | 没有合照准确率证据 | 准备 10 人以上合照，记录 TP/FP/FN、准确率、耗时 |
| 已完成 | `frontend/src/views/Statistics.vue` | 已增加活动参与趋势折线图 | 后续可继续补导出 CSV/Excel |
| 中 | `backend/app/services/face_service.py` | 阈值 `GROUP_FACE_SIMILARITY_THRESHOLD=0.55` 未调参记录 | 用真实数据调阈值，写入报告 |

---

## 五、情绪分析功能核查（8 分）

| 评分项 | 分值 | 状态 | 证据/说明 |
|---|---:|---|---|
| 考勤/合照过程中同步提取面部特征 | 2 | [基本完成] | 考勤图片和合照上传时调用 `analyze_image_emotion(s)`；人脸识别链路也提取 ArcFace 特征 |
| 完成情绪分类 | 3 | [基本完成] | `emotion_service.py` 接入 DeepFace 7 类情绪；失败时 fallback 为确定性演示分类 |
| 后端记录学号、姓名、识别时间、情绪类型 | 2 | [部分] | `Attendance` 记录时间和情绪，可关联学生；`ActivityParticipant` 记录情绪但没有单独情绪时间线接口，`/emotion/timeline` 目前只查考勤 |
| 前端查看统计结果 | 1 | [完成] | `Statistics.vue` 展示情绪分布图和考勤情绪时间线 |

**待补事项**

| 优先级 | 文件/位置 | 问题 | 建议 |
|---|---|---|---|
| 中 | `backend/app/routers/emotion.py` | `/emotion/timeline` 未包含合照情绪记录 | 合并 `ActivityParticipant` + `Activity` + `Student`，返回 group 场景的姓名、学号、活动时间、情绪 |
| 中 | `backend/app/routers/group.py` | 合照情绪分析按 DeepFace 返回顺序绑定匹配学生，未裁剪每个识别人脸后逐一分析 | 使用 InsightFace bbox 裁剪每张人脸，再分别做情绪分析，提高绑定准确性 |
| 中 | `README.md`/报告 | DeepFace fallback 会影响“真实情绪分类”得分 | 记录模型是否成功加载，演示前确保模型可用 |

---

## 六、系统安全性核查（18 分）

| 评分项 | 分值 | 状态 | 证据/说明 |
|---|---:|---|---|
| 活体检测抗照片伪造 | 7 | [部分偏弱] | 有动作活体前端，但可跳过；后端纹理模型无权重时默认通过 |
| 活体检测抗视频伪造 | 8 | [缺失/偏弱] | 仅眨眼/张嘴动作容易被视频重放绕过，缺随机挑战强制校验、纹理检测和重放防护 |
| 教师/学生权限区分 | 3 | [完成] | `require_teacher` 已用于学生管理、合照上传、批量导入；学生只能查看个人考勤、活动、情绪统计 |

**待补事项**

| 优先级 | 文件/位置 | 问题 | 建议 |
|---|---|---|---|
| 最高 | `backend/app/routers/attendance.py` | 活体挑战不是强制条件 | 没有有效 challenge 时拒绝考勤；challenge 必须一次性、短时有效、绑定用户 |
| 最高 | `frontend/src/views/Attendance.vue` | “跳过动作验证”会削弱安全项 | 生产/演示模式移除跳过按钮，或仅教师调试可用 |
| 高 | `liveness_service.py` | 抗照片/视频模型未闭环 | 接入可复现实验的 Silent-Face/CDCN 权重，报告中给攻击样例测试 |
| 高 | 报告/测试 | 缺攻击测试结果 | 准备真人、纸质照片、屏幕照片、视频重放四类样例，记录通过率/拒绝率 |

---

## 七、实验报告与源码提交核查（30 分）

| 评分项 | 分值 | 状态 | 证据/说明 |
|---|---:|---|---|
| 课程设计报告 | 20 | [部分] | 已有 `README.md`、`technical-api-document.md`、设计/计划文档，但缺正式报告中的测试用例、结果分析、准确率、性能、安全实验 |
| 源码完整、可部署 | 10 | [基本完成] | 前后端源码、依赖、启动脚本、部署文档基本齐全；注意不要提交 `venv`、`node_modules`、真实人脸照片和模型大文件 |

**待补事项**

| 优先级 | 文件/位置 | 问题 | 建议 |
|---|---|---|---|
| 高 | 课程设计报告 | 缺正式报告结构 | 按评分标准补：需求分析、系统设计、数据库设计、接口设计、算法设计、核心代码、测试用例、结果分析、总结展望 |
| 高 | 报告测试章节 | 缺准确率和性能数据 | 统计考勤识别、合照识别、情绪分类、活体攻击测试的样本数和指标 |
| 中 | `README.md`/`docs/deploy.md` | 需要明确模型下载、启动步骤、默认账号、常见问题 | 补充 `script/download_models.py --cpu`、`script/face_import.py` 的使用示例 |

---

## 八、按优先级排序的下一步任务

| 优先级 | 任务 | 目标分值影响 |
|---|---|---|
| P0 | 强制考勤必须通过 `action-challenge`，禁用普通图片绕过活体 | 系统安全 15 分，基础考勤后端 10 分 |
| P0 | 完成可演示的照片/视频攻击拒绝策略和测试记录 | 系统安全 15 分 |
| Done | 增加考勤记录日期筛选和导出日期范围 | 基础考勤前端/接口 |
| P1 | 做 10 人以上合照测试，记录准确率、耗时、失败原因 | 合照识别 3 分，报告结果分析 |
| P1 | 补正式课程设计报告 | 实验报告 20 分 |
| P2 | 合照情绪按人脸框裁剪逐一分析，补 group 情绪时间线 | 情绪分析 2-3 分 |
| P2 | 统计页继续增加导出功能 | 合照统计报表与报告展示 |
| P2 | 整理 `.gitignore`，排除模型、数据库、上传图片、依赖目录 | 源码提交规范 |

---

## 九、当前可展示亮点

| 功能 | 说明 |
|---|---|
| 真实人脸识别 | InsightFace SCRFD + ArcFace，支持单人照入库、签到匹配、合照多人识别 |
| 内存人脸库 | 服务启动加载 `face_feature`，上传/删除人脸时同步更新 |
| 中文路径读图修复 | `face_service.py` 使用 `np.fromfile + cv2.imdecode`，避免 Windows 中文路径下 `cv2.imread` 失败 |
| 情绪分析 | DeepFace 7 类情绪，失败时 fallback 保证流程可运行 |
| 权限隔离 | 教师/学生账号区分，学生数据按 `student_id` 过滤 |
| 快速启动 | `quick_start.py`、`quick-start.bat`、`run.ps1` 可辅助启动和检查环境 |
