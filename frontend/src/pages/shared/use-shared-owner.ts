import { useParams } from 'react-router-dom'

import { useFriends } from '@/features/friends/use-friends'

/**
 * De qui regarde-t-on les données.
 *
 * « Journal partagé » ne disait pas de qui : l'identifiant est dans l'URL, le
 * nom nulle part. Il est résolu depuis la liste d'amis, déjà en cache — plutôt
 * que par un endpoint de plus qui exposerait un compte par son seul numéro.
 *
 * `invalid` distingue une adresse malformée d'un chargement : `Number('abc')`
 * donne `NaN`, la requête reste désactivée, et l'écran affichait un squelette
 * qui ne se résolvait jamais.
 */
export function useSharedOwner(): { userId: number; name: string | null; invalid: boolean } {
  const params = useParams()
  const userId = Number(params.userId)
  const invalid = !Number.isFinite(userId)

  const friends = useFriends()
  const rows = Array.isArray(friends.data?.results) ? friends.data.results : []
  const owner = rows.find((friend) => friend.id === userId)

  return { userId, name: owner?.username ?? null, invalid }
}
