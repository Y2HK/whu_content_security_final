import { defineStore } from 'pinia'

import request from '../api/request'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: sessionStorage.getItem('attendance_token') || localStorage.getItem('attendance_token') || '',
    user: null,
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
  },
  actions: {
    async login(payload) {
      const { data } = await request.post('/auth/login', payload)
      this.token = data.data.access_token
      sessionStorage.setItem('attendance_token', this.token)
      localStorage.removeItem('attendance_token')
      await this.fetchCurrentUser()
    },
    async register(payload) {
      const { data } = await request.post('/auth/register', payload)
      this.token = data.data.access_token
      this.user = data.data.user
      sessionStorage.setItem('attendance_token', this.token)
      localStorage.removeItem('attendance_token')
      return this.user
    },
    async fetchCurrentUser() {
      const { data } = await request.get('/auth/me')
      this.user = data.data
      return this.user
    },
    async logout() {
      try {
        await request.post('/auth/logout')
      } finally {
        this.clearAuth()
      }
    },
    clearAuth() {
      this.token = ''
      this.user = null
      sessionStorage.removeItem('attendance_token')
      localStorage.removeItem('attendance_token')
    },
  },
})
