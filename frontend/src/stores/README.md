# stores 模块说明

## 职责
全局状态管理（Pinia），管理用户认证状态和登录信息。

## 文件说明

| 文件 | 职责 |
|------|------|
| `auth.js` | 认证状态：token、用户信息、登录态、登录/登出方法 |

## State 结构

```javascript
{
  token: localStorage.getItem('token') || null,
  user: null,           // { username, role, student_id }
  isLoggedIn: false
}
```

## Actions

| Action | 说明 |
|--------|------|
| `login(credentials)` | 调用 API 登录，存储 token 和用户信息 |
| `logout()` | 清除 token 和状态，跳转登录页 |
| `fetchUser()` | 获取当前用户信息并存储 |

## 使用方式

```javascript
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

// 登录
await auth.login({ username, password })

// 判断角色
if (auth.user?.role === 'teacher') { ... }

// 登出
auth.logout()
```
