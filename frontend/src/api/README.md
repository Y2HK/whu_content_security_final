# api 模块说明

## 职责
HTTP 请求封装，统一处理 BaseURL、JWT Token 注入、401 跳转。

## 文件说明

| 文件 | 职责 |
|------|------|
| `request.js` | Axios 实例封装：拦截器自动附加 Token、统一错误处理 |

## 拦截器逻辑

**请求拦截器：**
- 从 localStorage 读取 token
- 自动注入 `Authorization: Bearer <token>` 请求头

**响应拦截器：**
- 正常响应：直接返回 `res.data`
- 401 错误：清除 token，跳转登录页
- 其他错误：Promise.reject 抛出错误

## 使用方式

```javascript
import api from '@/api/request'

// GET 请求
const { data } = await api.get('/attendance/records')

// POST 请求（JSON）
await api.post('/auth/login', { username, password })

// POST 请求（文件上传）
const form = new FormData()
form.append('image', blob)
await api.post('/attendance/check', form, { headers: { 'Content-Type': 'multipart/form-data' }})
```
