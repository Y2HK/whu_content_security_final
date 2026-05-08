<template>
  <el-container class="app-shell">
    <template v-if="route.meta.requiresAuth && authStore.isLoggedIn">
      <el-aside width="220px" class="sidebar">
        <div class="logo">班级考勤系统</div>
        <el-menu :default-active="route.path" router>
          <el-menu-item index="/students">{{ isTeacher ? '学生管理' : '我的信息' }}</el-menu-item>
          <el-menu-item index="/attendance">基础考勤</el-menu-item>
          <el-menu-item index="/group">合照识别</el-menu-item>
          <el-menu-item index="/statistics">统计分析</el-menu-item>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header class="topbar">
          <div>最小可用版本</div>
          <div class="topbar-actions">
            <span>{{ authStore.user?.username || '未登录' }} · {{ roleLabel }}</span>
            <el-button type="danger" plain @click="handleLogout">退出</el-button>
          </div>
        </el-header>
        <el-main class="main-content">
          <router-view />
        </el-main>
      </el-container>
    </template>
    <template v-else>
      <router-view />
    </template>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const isTeacher = computed(() => authStore.user?.role === 'teacher')
const roleLabel = computed(() => (isTeacher.value ? '教师' : '学生'))

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.sidebar {
  background: #0f172a;
  color: #fff;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.main-content {
  background: #f8fafc;
}
</style>
