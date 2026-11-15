import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, apiErrorMessage, setAccessToken } from '@/api/client'

export interface AuthUser {
  uid: string
  nickname: string
  college: string
  gender: string
}

interface LoginResponse {
  access: string
  user?: AuthUser
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(null)
  const user = ref<AuthUser | null>(null)
  const loading = ref(false)
  const error = ref('')

  const isAuthenticated = computed(() => Boolean(accessToken.value))
  const isPreview = computed(() => accessToken.value === 'preview-only')

  async function fetchMe(): Promise<void> {
    const { data } = await api.get<AuthUser>('/auth/me/')
    user.value = data
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const { data } = await api.post<LoginResponse>('/auth/login/', { email, password })
      accessToken.value = data.access
      setAccessToken(data.access)
      if (data.user) {
        user.value = data.user
      } else {
        await fetchMe()
      }
    } catch (caught) {
      error.value = apiErrorMessage(caught)
      throw caught
    } finally {
      loading.value = false
    }
  }

  function logout(): void {
    accessToken.value = null
    user.value = null
    error.value = ''
    setAccessToken(null)
  }

  function startPreview(): void {
    accessToken.value = 'preview-only'
    setAccessToken('preview-only')
    user.value = {
      uid: '0000000000',
      nickname: '预览用户',
      college: '计算机学院',
      gender: '男',
    }
  }

  return {
    accessToken,
    user,
    loading,
    error,
    isAuthenticated,
    isPreview,
    login,
    logout,
    startPreview,
    fetchMe,
  }
})
