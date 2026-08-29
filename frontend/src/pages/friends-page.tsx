import { Check, Search, TriangleAlert, UserMinus, UserPlus, X } from 'lucide-react'
import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  MINIMUM_QUERY_LENGTH,
  useAnswerFriendRequest,
  useFriendRequests,
  useFriends,
  useRemoveFriend,
  useSendFriendRequest,
  useUserSearch,
} from '@/features/friends/use-friends'
import type { Friend, FriendRequest, UserSummary } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

function fullName(user: UserSummary): string {
  const name = `${user.first_name} ${user.last_name}`.trim()
  return name || user.username
}

function ErrorLine({ error }: { error: unknown }) {
  return (
    <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
      <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {describeError(error)}
    </p>
  )
}

function UserSearch() {
  const searchId = useId()
  const [query, setQuery] = useState('')

  const search = useUserSearch(query)
  const invite = useSendFriendRequest()

  const results = Array.isArray(search.data?.results) ? search.data.results : []

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={searchId}>Chercher quelqu’un</Label>
        <div className="relative">
          <Search
            aria-hidden="true"
            className="text-muted-foreground pointer-events-none absolute inset-y-0 left-3 my-auto size-4"
          />
          <Input
            id={searchId}
            className="pl-9"
            placeholder="nom d’utilisateur"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <p className="text-muted-foreground text-xs">
          La recherche porte sur le nom d’utilisateur, jamais sur l’adresse email.
        </p>
      </div>

      {invite.isError && <ErrorLine error={invite.error} />}

      {query.trim().length >= MINIMUM_QUERY_LENGTH && (
        <>
          {/* Une recherche en échec disait « Aucun compte trouvé » : un serveur
              en panne devenait « cette personne n'existe pas ». */}
          {search.error && <ErrorLine error={search.error} />}
          {!search.isPending && !search.error && results.length === 0 && (
            <p className="text-muted-foreground text-sm">Aucun compte trouvé.</p>
          )}
          <ul className="flex flex-col">
            {results.map((user) => (
              <li
                key={user.id}
                className="flex items-center justify-between gap-4 border-b py-2 last:border-b-0"
              >
                <span className="flex flex-col">
                  <span className="text-sm font-medium">{user.username}</span>
                  <span className="text-muted-foreground text-xs">{fullName(user)}</span>
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  aria-label={`Inviter ${user.username}`}
                  disabled={invite.isPending}
                  onClick={() =>
                    invite.mutate(user.id, {
                      onSuccess: () => toast.success('Demande envoyée.'),
                    })
                  }
                >
                  <UserPlus aria-hidden="true" className="size-4" />
                  Inviter
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function RequestRow({ request }: { request: FriendRequest }) {
  const answer = useAnswerFriendRequest()
  const other = request.direction === 'received' ? request.from_user : request.to_user

  return (
    <li className="flex items-center justify-between gap-4 border-b py-2 last:border-b-0">
      <span className="flex flex-col">
        <span className="text-sm font-medium">{other.username}</span>
        <span className="text-muted-foreground text-xs">
          {request.direction === 'received' ? 'vous a invité' : 'invitation envoyée'}
        </span>
      </span>

      {request.direction === 'received' && (
        <span className="flex gap-1">
          <Button
            type="button"
            size="sm"
            aria-label={`Accepter ${other.username}`}
            disabled={answer.isPending}
            onClick={() =>
              answer.mutate(
                { id: request.id, accept: true },
                { onSuccess: () => toast.success('Vous êtes amis.') },
              )
            }
          >
            <Check aria-hidden="true" className="size-4" />
            Accepter
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={`Refuser ${other.username}`}
            disabled={answer.isPending}
            onClick={() =>
              answer.mutate(
                { id: request.id, accept: false },
                { onSuccess: () => toast.success('Demande refusée.') },
              )
            }
          >
            <X aria-hidden="true" className="size-4" />
          </Button>
        </span>
      )}
    </li>
  )
}

/**
 * Un ami, et ce qu'il m'a ouvert.
 *
 * Les deux liens ne s'affichent que si le partage existe. Ils étaient
 * inconditionnels : chez un ami qui n'avait rien ouvert, le backend répondait
 * 404 — correctement, la spec 04 §13 bis l'impose pour ne pas révéler
 * l'existence d'une donnée fermée — et l'utilisateur voyait une erreur là où
 * il attendait un journal.
 *
 * La réponse ne se déduit donc pas du 404, qui couvre aussi le compte suspendu
 * et l'incident serveur : elle vient de mes propres accès, que `GET /friends/`
 * renvoie avec chaque ami.
 */
function FriendRow({ friend }: { friend: Friend }) {
  const remove = useRemoveFriend()
  const opened = friend.shares_diary || friend.shares_progress

  return (
    <li className="flex flex-col gap-2 border-b py-3 last:border-b-0">
      <div className="flex items-center justify-between gap-4">
        <span className="flex flex-col">
          <span className="text-sm font-medium">{friend.username}</span>
          <span className="text-muted-foreground text-xs">{fullName(friend)}</span>
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-destructive"
          aria-label={`Retirer ${friend.username}`}
          disabled={remove.isPending}
          onClick={() =>
            remove.mutate(friend.id, {
              onSuccess: () =>
                // La révocation fait partie du retrait : le dire évite la
                // surprise de découvrir qu'un partage a survécu ou disparu.
                toast.success('Ami retiré. Les partages qui le visaient sont révoqués.'),
            })
          }
        >
          <UserMinus aria-hidden="true" className="size-4" />
          Retirer
        </Button>
      </div>

      {opened ? (
        <div className="flex flex-wrap gap-2">
          {friend.shares_diary && (
            <Button asChild variant="outline" size="sm">
              <Link to={`/amis/${friend.id}/journal`}>Son journal</Link>
            </Button>
          )}
          {friend.shares_progress && (
            <Button asChild variant="outline" size="sm">
              <Link to={`/amis/${friend.id}/progression`}>Sa progression</Link>
            </Button>
          )}
        </div>
      ) : (
        <p className="text-muted-foreground text-xs">
          {friend.username} ne vous a ouvert ni son journal ni sa progression.
        </p>
      )}
    </li>
  )
}

/** Amis et demandes (spec 01 §17). */
export function FriendsPage() {
  const friends = useFriends()
  const requests = useFriendRequests()

  const friendRows = Array.isArray(friends.data?.results) ? friends.data.results : []
  const requestRows = Array.isArray(requests.data?.results) ? requests.data.results : []

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Amis</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Partager suppose d’être amis : retirer quelqu’un révoque ce qu’on lui avait ouvert.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Ajouter
          </CardTitle>
        </CardHeader>
        <CardContent>
          <UserSearch />
        </CardContent>
      </Card>

      {requests.error && (
        <Card>
          <CardHeader>
            <CardTitle as="h2" className="text-base">
              Demandes
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Sans cela, une panne se lisait comme « aucune demande » — et la
                pastille de navigation restait muette. */}
            <ErrorLine error={requests.error} />
          </CardContent>
        </Card>
      )}

      {requestRows.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle as="h2" className="text-base">
              Demandes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col">
              {requestRows.map((request) => (
                <RequestRow key={request.id} request={request} />
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle as="h2" className="text-base">
            Mes amis
          </CardTitle>
          {friendRows.length === 0 && !friends.isPending && (
            <CardDescription>
              Personne pour l’instant. Cherchez un nom d’utilisateur pour envoyer une invitation.
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          {friends.isPending && (
            <div aria-busy="true">
              <div className="bg-muted h-16 animate-pulse rounded-xl" />
              <span className="sr-only">Chargement des amis…</span>
            </div>
          )}
          {friends.error && <ErrorLine error={friends.error} />}
          {friendRows.length > 0 && (
            <ul className="flex flex-col">
              {friendRows.map((friend) => (
                <FriendRow key={friend.id} friend={friend} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
