import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AppNotification, NotificationPreference, Reminder } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { BASE_ROUTES, paginated } from '@/test/recipes'
import { renderRoute } from '@/test/render'

function notification(overrides: Partial<AppNotification> = {}): AppNotification {
  return {
    id: 7,
    event_type: 'friend_request',
    event_label: "Demande d'ami reçue",
    title: 'alice souhaite vous ajouter',
    message: 'Vous pouvez accepter ou refuser depuis la page Amis.',
    link: '/amis',
    is_read: false,
    created_at: '2026-08-30T08:00:00Z',
    ...overrides,
  }
}

function preference(overrides: Partial<NotificationPreference> = {}): NotificationPreference {
  return {
    event_type: 'meal_reminder',
    event_label: 'Rappel de repas',
    in_app_enabled: true,
    email_enabled: false,
    push_enabled: false,
    ...overrides,
  }
}

function reminder(overrides: Partial<Reminder> = {}): Reminder {
  return {
    id: 3,
    reminder_type: 'weigh_in',
    type_label: 'Pesée',
    time: '08:00:00',
    days_of_week: [0, 1, 2, 3, 4],
    enabled: true,
    created_at: '2026-08-30T08:00:00Z',
    updated_at: '2026-08-30T08:00:00Z',
    ...overrides,
  }
}

interface Stubs {
  notifications?: AppNotification[]
  unread?: number
  reminders?: Reminder[]
  preferences?: NotificationPreference[]
  onList?: () => Response
}

function stub({
  notifications = [notification()],
  unread = 1,
  reminders = [],
  preferences = [preference()],
  onList,
}: Stubs = {}) {
  return stubFetch(
    [
      ...BASE_ROUTES,
      {
        match: '/notification-preferences/',
        respond: () => jsonResponse({ results: preferences }),
      },
      {
        match: '/notifications/',
        respond: onList ?? (() => jsonResponse({ ...paginated(notifications), unread })),
      },
      { match: '/reminders/', respond: () => jsonResponse(paginated(reminders)) },
    ],
    () => jsonResponse(paginated([])),
  )
}

beforeEach(() => {
  seedCsrfCookie()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
})

describe('notifications', () => {
  it('affiche les notifications reçues', async () => {
    stub()
    renderRoute('/notifications')

    const list = await screen.findByRole('list', { name: 'Notifications' })
    expect(within(list).getByText('alice souhaite vous ajouter')).toBeInTheDocument()
    expect(within(list).getByRole('link', { name: 'Ouvrir' })).toHaveAttribute('href', '/amis')
  })

  it('marque une notification comme lue', async () => {
    const user = userEvent.setup()
    const spy = stub()
    renderRoute('/notifications')
    await screen.findByRole('list', { name: 'Notifications' })

    await user.click(screen.getByRole('button', { name: /Marquer .* comme lue/ }))

    await waitFor(() => {
      const call = spy.mock.calls.find(
        ([url, init]) => String(url).includes('/notifications/7/read/') && init?.method === 'POST',
      )
      expect(call).toBeDefined()
    })
  })

  it('n’offre pas de tout marquer lu quand rien n’est non lu', async () => {
    stub({ notifications: [notification({ is_read: true })], unread: 0 })
    renderRoute('/notifications')
    await screen.findByRole('list', { name: 'Notifications' })

    expect(screen.queryByRole('button', { name: /Tout marquer/ })).not.toBeInTheDocument()
  })

  it('porte une pastille sur l’entrée de navigation', async () => {
    stub({ unread: 3 })
    renderRoute('/notifications')

    expect(await screen.findAllByLabelText('3 notifications non lues')).not.toHaveLength(0)
  })

  it('propose un état vide explicite', async () => {
    stub({ notifications: [], unread: 0 })
    renderRoute('/notifications')

    expect(await screen.findByText(/Rien pour l’instant/)).toBeInTheDocument()
  })

  it('signale une erreur sans casser l’écran', async () => {
    stub({
      onList: () =>
        jsonResponse({ code: 'server_error', message: 'Erreur serveur.', errors: {} }, 500),
    })
    renderRoute('/notifications')

    expect(await screen.findByRole('alert')).toHaveTextContent(/Erreur serveur/)
  })
})

describe('préférences', () => {
  it('affiche la case push désactivée, avec sa raison', async () => {
    // Une case qui ne fait rien est pire qu'une case grisée.
    stub()
    renderRoute('/notifications')

    const push = await screen.findByLabelText('Rappel de repas — push')
    expect(push).toBeDisabled()
    expect(screen.getByText(/canal push n’est pas encore disponible/)).toBeInTheDocument()
  })

  it('enregistre un changement de canal', async () => {
    const user = userEvent.setup()
    const spy = stub()
    renderRoute('/notifications')

    await user.click(await screen.findByLabelText('Rappel de repas — email'))

    await waitFor(() => {
      const call = spy.mock.calls.find(
        ([url, init]) =>
          String(url).includes('/notification-preferences/') && init?.method === 'PATCH',
      )
      expect(JSON.parse(String(call?.[1]?.body)).results[0].email_enabled).toBe(true)
    })
  })
})

describe('rappels', () => {
  it('propose les trois types, même sans rappel réglé', async () => {
    stub()
    renderRoute('/notifications')

    // Nommés : « Planification » figure aussi dans la navigation.
    expect(await screen.findByRole('listitem', { name: 'Rappel Pesée' })).toBeInTheDocument()
    expect(screen.getByRole('listitem', { name: 'Rappel Repas' })).toBeInTheDocument()
    expect(screen.getByRole('listitem', { name: 'Rappel Planification' })).toBeInTheDocument()
  })

  it('reprend l’heure et les jours d’un rappel existant', async () => {
    stub({ reminders: [reminder()] })
    renderRoute('/notifications')

    const row = await screen.findByRole('listitem', { name: 'Rappel Pesée' })
    expect(within(row).getByLabelText('Heure')).toHaveValue('08:00')
    // Du lundi au vendredi : samedi et dimanche ne sont pas retenus.
    expect(within(row).getByLabelText('Pesée — dimanche')).toHaveAttribute('aria-pressed', 'false')
    expect(within(row).getByLabelText('Pesée — lundi')).toHaveAttribute('aria-pressed', 'true')
  })

  it('enregistre un rappel avec ses jours', async () => {
    const user = userEvent.setup()
    const spy = stub()
    renderRoute('/notifications')

    await user.click(await screen.findByRole('button', { name: 'Activer le rappel Repas' }))

    await waitFor(() => {
      const call = spy.mock.calls.find(
        ([url, init]) => String(url).includes('/reminders/') && init?.method === 'POST',
      )
      expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ reminder_type: 'meal' })
    })
  })
})
