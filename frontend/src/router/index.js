import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import LoginView from '../views/Login.vue'
import StudentManageView from '../views/StudentManage.vue'
import AttendanceView from '../views/Attendance.vue'
import GroupPhotoView from '../views/GroupPhoto.vue'
import StatisticsView from '../views/Statistics.vue'

const routes = [
  { path: '/', redirect: '/students' },
  { path: '/login', component: LoginView, meta: { guestOnly: true } },
  { path: '/students', component: StudentManageView, meta: { requiresAuth: true } },
  { path: '/attendance', component: AttendanceView, meta: { requiresAuth: true } },
  { path: '/group', component: GroupPhotoView, meta: { requiresAuth: true } },
  { path: '/statistics', component: StatisticsView, meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  if (authStore.token && !authStore.user) {
    try {
      await authStore.fetchCurrentUser()
    } catch {
      authStore.clearAuth()
    }
  }

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    return '/login'
  }

  if (to.meta.guestOnly && authStore.isLoggedIn) {
    return '/students'
  }

  return true
})

export default router
