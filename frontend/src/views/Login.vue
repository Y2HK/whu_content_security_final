<template>
  <div class="login-page">
    <el-card class="login-card">
      <template #header>
        <div class="title-wrap">
          <h2>班级考勤系统</h2>
          <p>基础版登录</p>
        </div>
      </template>
      <el-form :model="form" @submit.prevent="handleLogin">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="full-btn" @click="handleLogin">
          登录
        </el-button>
        <el-alert class="tips" type="info" :closable="false" title="默认教师账号：teacher / teacher123" />
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const form = reactive({
  username: 'teacher',
  password: 'teacher123',
})

const handleLogin = async () => {
  loading.value = true
  try {
    await authStore.login(form)
    ElMessage.success('登录成功')
    router.push('/students')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #dbeafe, #eff6ff);
}

.login-card {
  width: 420px;
}

.title-wrap {
  text-align: center;
}

.full-btn {
  width: 100%;
}

.tips {
  margin-top: 16px;
}
</style>
