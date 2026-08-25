import { api } from '@/lib/api/client'
import type { AuthUser, DetailResponse, Profile, UserSettings } from '@/lib/api/types'

export const meQueryKey = ['auth', 'me'] as const
export const settingsQueryKey = ['profile', 'settings'] as const

export interface LoginPayload {
  username: string
  password: string
}

export interface RegistrationPayload {
  first_name: string
  last_name: string
  username: string
  email?: string
  password: string
  password_confirmation: string
}

export interface ChangePasswordPayload {
  current_password: string
  new_password: string
  new_password_confirmation: string
}

export interface ResetPasswordPayload {
  uid: string
  token: string
  new_password: string
  new_password_confirmation: string
}

export const fetchMe = () => api.get<AuthUser>('/auth/me/')

export const login = (payload: LoginPayload) => api.post<AuthUser>('/auth/login/', payload)

export const logout = () => api.post<void>('/auth/logout/')

export const logoutAll = () => api.post<void>('/auth/logout-all/')

export const requestRegistration = (payload: RegistrationPayload) =>
  api.post<DetailResponse>('/auth/register-request/', payload)

export const forgotPassword = (username: string) =>
  api.post<DetailResponse>('/auth/forgot-password/', { username })

export const resetPassword = (payload: ResetPasswordPayload) =>
  api.post<DetailResponse>('/auth/reset-password/', payload)

export const changePassword = (payload: ChangePasswordPayload) =>
  api.post<DetailResponse>('/account/change-password/', payload)

export const deleteAccount = (usernameConfirmation: string) =>
  api.delete<void>('/account/', { username_confirmation: usernameConfirmation })

export const fetchProfile = () => api.get<Profile>('/profile/')

export const updateProfile = (payload: Partial<Profile>) => api.patch<Profile>('/profile/', payload)

export const fetchSettings = () => api.get<UserSettings>('/profile/settings/')

export const updateSettings = (payload: Partial<UserSettings>) =>
  api.patch<UserSettings>('/profile/settings/', payload)
