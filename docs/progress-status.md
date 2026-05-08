# 班级考勤系统基础版进度说明

> 交付范围：最小可用版本系统 + 进度说明文档  
> 当前阶段：除“真实人脸识别模型接入、活体检测、细粒度权限控制、抗攻击能力”外，其余基础版工作已完成。

---

## 1. 当前已完成内容

### 1.1 文档层

已完成以下文档与交付说明：

1. `2026-04-28-class-attendance-system-design.md`  
   已改为“基础版可实现方案”，明确实现边界与预留接口。

2. `2026-04-28-class-attendance-system-plan.md`  
   已改为“基础版实施计划”，按最小可用系统分阶段推进。

3. `progress-status.md`  
   持续同步当前实现进度、预留能力和剩余范围。

4. `README.md`、`docs/deploy.md`  
   已补充项目说明、启动步骤、演示流程与版本说明。

### 1.2 后端工程基础设施

已完成：

- `backend/requirements.txt`
- `backend/.env.example`
- `backend/run.py`
- `backend/setup.bat`
- `backend/run_tests.bat`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/security.py`
- `backend/app/core/dependencies.py`
- `backend/app/db/database.py`
- `backend/app/db/models.py`
- `backend/app/db/init_db.py`

能力说明：

- 可启动 FastAPI 服务；
- 启动时自动建表；
- 自动初始化默认教师账号 `teacher / teacher123`；
- 提供健康检查接口与 Swagger 文档入口；
- 已补充基础测试运行脚本。

### 1.3 已完成后端业务接口

#### 认证模块

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`

#### 学生管理模块

- `GET /api/v1/students`
- `POST /api/v1/students`
- `PUT /api/v1/students/{id}`
- `DELETE /api/v1/students/{id}`
- `POST /api/v1/students/{id}/face`
- `POST /api/v1/students/batch`

#### 基础考勤模块

- `POST /api/v1/attendance/check`
- `GET /api/v1/attendance/records`
- `GET /api/v1/attendance/export`
- `GET /api/v1/attendance/action-challenge`

#### 合照识别模块

- `POST /api/v1/group/upload`
- `GET /api/v1/group/activities`
- `GET /api/v1/group/activities/{id}`
- `GET /api/v1/group/statistics`

#### 情绪统计模块

- `GET /api/v1/emotion/statistics`
- `GET /api/v1/emotion/timeline`

### 1.4 已完成的数据结构

已建立以下数据表：

- `user`
- `student`
- `face_feature`
- `attendance`
- `activity`
- `activity_participant`

### 1.5 已完成的服务层封装与占位能力

当前为了保证最小可用版本可交付，算法部分采用了服务封装 + 占位实现：

- `face_service.py`：提供基础识别占位逻辑；
- `emotion_service.py`：提供简化情绪结果；
- `liveness_service.py`：保留活体检测占位接口。

这样做的目的是：

1. 先把业务流程打通；
2. 保证前后端联调接口稳定；
3. 后续可直接替换为真实识别模型。

### 1.6 已完成前端基础页面与路由

已完成：

- `frontend/package.json`
- `frontend/vite.config.js`
- `frontend/index.html`
- `frontend/.env.local`
- `frontend/sample-students.csv`
- `frontend/src/main.js`
- `frontend/src/App.vue`
- `frontend/src/router/index.js`
- `frontend/src/api/request.js`
- `frontend/src/stores/auth.js`
- `frontend/src/components/CameraCapture.vue`
- `frontend/src/components/FaceMeshDetector.vue`
- `frontend/src/components/EmotionChart.vue`
- `frontend/src/views/Login.vue`
- `frontend/src/views/StudentManage.vue`
- `frontend/src/views/Attendance.vue`
- `frontend/src/views/GroupPhoto.vue`
- `frontend/src/views/Statistics.vue`

能力说明：

- 已完成登录页与认证状态管理；
- 已完成基础路由守卫；
- 已完成学生管理、基础考勤、合照识别、统计分析页面；
- 已完成浏览器摄像头拍照采集；
- 已完成图片上传考勤与摄像头拍照考勤双流程；
- 已完成示例 CSV 下载、批量导入、数据导出等交互。

### 1.7 当前联调状态

当前前后端接口映射关系已完成：

- 登录页 对接 `/auth/login`、`/auth/me`、`/auth/logout`
- 学生管理页 对接 `/students`、`/students/{id}`、`/students/{id}/face`、`/students/batch`
- 考勤页 对接 `/attendance/check`、`/attendance/records`、`/attendance/export`
- 合照识别页 对接 `/group/upload`、`/group/activities`、`/group/activities/{id}`
- 统计页 对接 `/emotion/statistics`、`/emotion/timeline`、`/group/statistics`

当前联调说明：

- 接口路径、参数格式、鉴权头部已统一；
- 前端与后端最近编辑文件诊断检查已通过；
- 后端主干代码已通过编译检查；
- 当前版本已达到“可启动、可联调、可演示”的基础版交付状态。

### 1.8 已完成测试、脚本与交付辅助内容

已完成：

- `backend/tests/conftest.py`
- `backend/tests/test_health.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_students.py`
- `docs/deploy.md`
- `docs/sample-students.csv`
- `README.md`
- `start-guide.bat`

能力说明：

- 已具备基础接口测试样例；
- 已提供后端测试脚本；
- 已提供示例 CSV 数据；
- 已提供部署说明与快速启动说明；
- 已满足课程设计源码提交与运行说明的基础要求。

---

## 2. 当前未完成内容

本项目当前仅保留以下未完成项，这些内容也是本阶段明确排除的范围：

### 2.1 真实算法能力未完成

- 真实人脸识别模型接入
- 真实多人脸检测与高精度合照识别
- 高精度情绪分析模型接入

### 2.2 活体检测未完成

- 动作活体检测真实接入
- 纹理活体检测真实接入
- 活体结果参与后端安全判定

### 2.3 细粒度权限控制未完成

- 学生端个人数据隔离
- 教师/学生路由级权限限制全覆盖
- 前端页面级权限差异展示

### 2.4 抗攻击能力未完成

- 抗照片攻击能力
- 抗视频重放攻击能力
- 时序一致性与伪造检测能力

---

## 3. 已预留接口与扩展说明

### 3.1 权限相关预留

已预留：

- `role` 角色字段
- `student_id` 关联字段
- `require_teacher` 依赖函数

后续可直接在路由上增加教师权限限制，并对学生接口做数据过滤。

### 3.2 抗攻击与活体检测相关预留

已预留：

- `GET /api/v1/attendance/action-challenge`
- `liveness_service.py`
- `attendance.is_live`
- `attendance.live_method`
- 前端自动抓拍与人脸框交互占位组件

当前接口与组件用于说明系统结构已经为活体检测与安全增强留出扩展点。

### 3.3 算法替换扩展点

已预留：

- `face_service.py`
- `emotion_service.py`
- `liveness_service.py`

后续只需替换服务层实现，无需大规模改动路由与数据库结构。

---

## 4. 当前版本说明

### 4.1 当前版本性质

当前版本属于“课程设计基础版完整交付版本（排除真实识别、活体、细粒度权限、抗攻击能力）”，特点如下：

- 前后端结构完整；
- 主要业务接口齐全；
- 页面与路由已可使用；
- 支持学生管理、考勤、合照、统计、导出、示例导入；
- 可启动、可调试、可演示、可继续扩展。

### 4.2 当前版本局限

- 识别与情绪结果为简化实现，不代表最终算法精度；
- 合照识别为占位逻辑，不代表真实检测效果；
- 权限控制和抗攻击能力仅保留接口与数据结构；
- 自动抓拍、人脸框与活体判断当前仍为交互占位。

---

## 5. 结论

截至当前阶段，除以下四类能力外，其余课程设计基础版工作已完成：

1. 真实人脸识别模型接入
2. 活体检测
3. 细粒度权限控制
4. 抗攻击能力

这意味着当前项目已经具备：

- 课程设计基础功能演示能力；
- 源码提交能力；
- 部署与运行说明；
- 后续继续替换算法和增强安全能力的工程基础。
