import { defineStore } from 'pinia'

import request from '../api/request'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('attendance_token') || '',
    user: null,
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
  },
  actions: {
    async login(payload) {
      const { data } = await request.post('/auth/login', payload)
      this.token = data.data.access_token
      localStorage.setItem('attendance_token', this.token)
      await this.fetchCurrentUser()
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
      localStorage.removeItem('attendance_token')
    },
  },
})
