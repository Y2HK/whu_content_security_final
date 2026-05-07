<template>
  <div class="login-page">
    <el-card class="login-card">
      <template #header>
        <div class="title-wrap">
          <h2>班级考勤系统</h2>
          <p>账号登录 / 注册</p>
        </div>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" @submit.prevent="handleLogin">
            <el-form-item label="用户名">
              <el-input v-model="loginForm.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="loginForm.password" type="password" show-password placeholder="请输入密码" />
            </el-form-item>
            <el-button type="primary" :loading="loading" class="full-btn" @click="handleLogin">
              登录
            </el-button>
            <el-alert class="tips" type="info" :closable="false" title="默认教师账号：teacher / teacher123" />
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form :model="registerForm" @submit.prevent="handleRegister">
            <el-form-item label="身份">
              <el-radio-group v-model="registerForm.role">
                <el-radio-button label="teacher">教师</el-radio-button>
                <el-radio-button label="student">学生</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="用户名">
              <el-input v-model="registerForm.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="registerForm.password" type="password" show-password placeholder="至少 6 位" />
            </el-form-item>
            <el-form-item v-if="registerForm.role === 'student'" label="学号">
              <el-input v-model="registerForm.student_no" placeholder="请输入已导入的学号" />
            </el-form-item>
            <el-button type="primary" :loading="loading" class="full-btn" @click="handleRegister">
              注册并登录
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
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
const activeTab = ref('login')
const loginForm = reactive({
  username: 'teacher',
  password: 'teacher123',
})
const registerForm = reactive({
  username: '',
  password: '',
  role: 'student',
  student_no: '',
})

const handleLogin = async () => {
  loading.value = true
  try {
    await authStore.login(loginForm)
    ElMessage.success('登录成功')
    router.push('/students')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  loading.value = true
  try {
    const payload = {
      username: registerForm.username,
      password: registerForm.password,
      role: registerForm.role,
    }
    if (registerForm.role === 'student') {
      payload.student_no = registerForm.student_no
    }

    await authStore.register(payload)
    ElMessage.success('注册成功')
    router.push('/students')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '注册失败')
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
