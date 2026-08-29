import { api } from '@/lib/api/client'
import type { Friend, FriendRequest, Paginated, UserSummary } from '@/lib/api/types'

export const friendsQueryKey = ['friends'] as const
export const friendRequestsQueryKey = ['friends', 'requests'] as const
export const userSearchQueryKey = (query: string) => ['friends', 'search', query] as const

export const searchUsers = (query: string) =>
  api.get<Paginated<UserSummary>>('/users/search/', { params: { q: query } })

export const fetchFriends = () => api.get<Paginated<Friend>>('/friends/')

/** Retire un ami **et** révoque les partages qui le visaient (spec 01 §17). */
export const removeFriend = (userId: number) => api.delete<void>(`/friends/${userId}/`)

export const fetchFriendRequests = () => api.get<Paginated<FriendRequest>>('/friend-requests/')

export const sendFriendRequest = (userId: number) =>
  api.post<FriendRequest>('/friend-requests/', { to_user_id: userId })

export const acceptFriendRequest = (id: number) => api.post<void>(`/friend-requests/${id}/accept/`)

export const rejectFriendRequest = (id: number) => api.post<void>(`/friend-requests/${id}/reject/`)
