import axios from 'axios'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 20000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('attendance_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('attendance_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default request
