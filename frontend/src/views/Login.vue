<template>
  <div class="login-page">
    <div class="login-shell">
      <section class="visual-panel" aria-hidden="true">
        <img class="login-visual" :src="loginVisual" alt="" />
      </section>

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
              <el-form-item v-if="registerForm.role === 'teacher'" label="工号">
                <el-input v-model="registerForm.teacher_no" placeholder="请输入教师工号（演示可任意填写）" />
              </el-form-item>
              <el-button type="primary" :loading="loading" class="full-btn" @click="handleRegister">
                注册并登录
              </el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import loginVisual from '../assets/login-visual.svg'
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
  teacher_no: '',
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
    } else {
      payload.teacher_no = registerForm.teacher_no
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
  width: 100vw;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background: linear-gradient(135deg, #dbeafe 0%, #f8fafc 52%, #dcfce7 100%);
  box-sizing: border-box;
}

.login-shell {
  width: min(960px, 100%);
  min-height: 560px;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) 420px;
  overflow: hidden;
  border-radius: 22px;
  background: #ffffff;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.16);
}

.visual-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 42px;
  background:
    radial-gradient(circle at 18% 18%, rgba(56, 189, 248, 0.18), transparent 32%),
    linear-gradient(145deg, #eff6ff 0%, #f0fdfa 100%);
}

.login-visual {
  width: 100%;
  max-width: 440px;
  display: block;
}

.login-card {
  width: auto;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}

.login-card :deep(.el-card__header) {
  padding: 34px 34px 8px;
  border-bottom: 0;
}

.login-card :deep(.el-card__body) {
  padding: 0 34px 34px;
}

.title-wrap {
  text-align: center;
}

.title-wrap h2 {
  margin: 0;
  font-size: 26px;
  color: #0f172a;
}

.title-wrap p {
  margin: 8px 0 0;
  color: #64748b;
}

.full-btn {
  width: 100%;
}

.tips {
  margin-top: 16px;
}

@media (max-width: 860px) {
  .login-page {
    padding: 18px;
  }

  .login-shell {
    grid-template-columns: 1fr;
    min-height: 0;
  }

  .visual-panel {
    min-height: 220px;
    padding: 24px;
  }

  .login-visual {
    max-width: 330px;
  }

  .login-card :deep(.el-card__header) {
    padding: 24px 24px 8px;
  }

  .login-card :deep(.el-card__body) {
    padding: 0 24px 26px;
  }
}
</style>
