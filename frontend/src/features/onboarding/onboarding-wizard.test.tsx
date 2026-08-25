import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { CalorieEstimate } from '@/lib/api/types'
import { clearCsrfCookie, jsonResponse, seedCsrfCookie, stubFetch } from '@/test/fetch-mock'
import { renderRoute } from '@/test/render'

const PENDING_ONBOARDING_USER = {
  id: 1,
  username: 'teo',
  first_name: 'Téo',
  last_name: 'Maitrot',
  email: null,
  status: 'ACTIVE',
  is_staff: false,
  onboarding_completed: false,
}

const ESTIMATE: CalorieEstimate = {
  bmr: '1780.00',
  tdee: '2759.00',
  daily_calories: '2209.00',
  protein_g: '166.00',
  carbs_g: '221.00',
  fat_g: '74.00',
  warnings: [],
  notice: 'Il s’agit d’une estimation et non d’une recommandation médicale.',
}

interface StubOptions {
  estimate?: CalorieEstimate
  onSubmit?: () => void
}

function stubOnboarding({ estimate = ESTIMATE, onSubmit }: StubOptions = {}) {
  let completed = false

  return stubFetch([
    {
      match: '/auth/me/',
      respond: () => jsonResponse({ ...PENDING_ONBOARDING_USER, onboarding_completed: completed }),
    },
    { match: '/profile/goals/calculate/', respond: () => jsonResponse(estimate) },
    {
      match: '/profile/onboarding/',
      respond: () => {
        completed = true
        onSubmit?.()
        return jsonResponse({ goal: { id: 1 }, warnings: [], notice: ESTIMATE.notice }, 201)
      },
    },
    {
      match: '/profile/settings/',
      respond: () =>
        jsonResponse({ language: 'fr', theme_mode: 'system', date_format: 'DD/MM/YYYY' }),
    },
    {
      match: '/health/',
      respond: () =>
        jsonResponse({
          status: 'ok',
          version: '0.1.0',
          time: '',
          checks: { database: 'ok', cache: 'ok' },
        }),
    },
  ])
}

/** Remplit l'étape « Profil » avec des valeurs valides. */
async function fillProfile(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Date de naissance'), '1996-01-01')
  await user.selectOptions(screen.getByLabelText('Sexe utilisé pour le calcul'), 'MALE')
  await user.type(screen.getByLabelText('Taille'), '180')
  await user.type(screen.getByLabelText('Poids actuel'), '80')
}

const next = async (user: ReturnType<typeof userEvent.setup>) =>
  user.click(await screen.findByRole('button', { name: /Continuer/ }))

beforeEach(() => {
  seedCsrfCookie()
  window.sessionStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCsrfCookie()
  window.sessionStorage.clear()
})

describe('Onboarding', () => {
  it('démarre sur l’étape profil', async () => {
    stubOnboarding()
    renderRoute('/onboarding')

    expect(
      await screen.findByRole('heading', { name: 'Configurons vos objectifs' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Étape 1 sur 7/)).toBeInTheDocument()
    expect(screen.getByLabelText('Date de naissance')).toBeInTheDocument()
  })

  it('bloque l’avancement tant que l’étape est incomplète', async () => {
    const user = userEvent.setup()
    stubOnboarding()
    renderRoute('/onboarding')

    await next(user)

    expect(await screen.findByText('La date de naissance est obligatoire.')).toBeInTheDocument()
    expect(screen.getByText(/Étape 1 sur 7/)).toBeInTheDocument()
  })

  it('refuse une personne de moins de 18 ans', async () => {
    const user = userEvent.setup()
    stubOnboarding()
    renderRoute('/onboarding')

    const recent = new Date()
    recent.setFullYear(recent.getFullYear() - 12)
    await user.type(
      await screen.findByLabelText('Date de naissance'),
      recent.toISOString().slice(0, 10),
    )
    await next(user)

    expect(await screen.findByText(/18 ans et plus/)).toBeInTheDocument()
  })

  it('avance jusqu’au calcul et affiche la mention obligatoire', async () => {
    const user = userEvent.setup()
    stubOnboarding()
    renderRoute('/onboarding')

    await fillProfile(user)
    await next(user) // objectif
    await user.click(await screen.findByRole('radio', { name: /Perdre du poids/ }))
    await next(user) // activité
    await user.click(await screen.findByRole('radio', { name: /Modérément actif/ }))
    await next(user) // rythme
    await user.click(await screen.findByRole('radio', { name: /0,5 kg par semaine/ }))
    await next(user) // calories

    expect(await screen.findByText('2209 kcal')).toBeInTheDocument()
    // Mention imposée par la spec 01 §3.
    expect(screen.getByText(/estimation et non d’une recommandation médicale/)).toBeInTheDocument()
  })

  it('affiche les avertissements sans bloquer', async () => {
    const user = userEvent.setup()
    stubOnboarding({
      estimate: { ...ESTIMATE, warnings: ['Un rythme de 1.5 kg par semaine est ambitieux.'] },
    })
    renderRoute('/onboarding')

    await fillProfile(user)
    await next(user)
    await user.click(await screen.findByRole('radio', { name: /Perdre du poids/ }))
    await next(user)
    await user.click(await screen.findByRole('radio', { name: /Modérément actif/ }))
    await next(user)
    await user.click(await screen.findByRole('radio', { name: /1 kg par semaine/ }))
    await next(user)

    expect(await screen.findByText(/ambitieux/)).toBeInTheDocument()
    // L'avertissement n'empêche pas de continuer (spec 01 §3).
    expect(screen.getByRole('button', { name: /Continuer/ })).toBeEnabled()
  })

  it('permet de remplacer les calories proposées', async () => {
    const user = userEvent.setup()
    stubOnboarding()
    renderRoute('/onboarding')

    await fillProfile(user)
    await next(user)
    await user.click(await screen.findByRole('radio', { name: /Maintenir mon poids/ }))
    await next(user)
    await user.click(await screen.findByRole('radio', { name: /Sédentaire/ }))
    await next(user) // rythme : non applicable en maintien
    expect(await screen.findByText(/aucun rythme n’est nécessaire/)).toBeInTheDocument()
    await next(user) // calories

    await user.click(await screen.findByRole('button', { name: /Définir moi-même mes calories/ }))
    const field = screen.getByLabelText('Objectif calorique')
    await user.clear(field)
    await user.type(field, '1900')

    expect(field).toHaveValue(1900)
  })

  it('enregistre le parcours complet et rejoint l’accueil', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    stubOnboarding({ onSubmit })
    const { router } = renderRoute('/onboarding')

    await fillProfile(user)
    await next(user)
    await user.click(await screen.findByRole('radio', { name: /Maintenir mon poids/ }))
    await next(user)
    await user.click(await screen.findByRole('radio', { name: /Sédentaire/ }))
    await next(user)
    await next(user) // calories
    await screen.findByText('2209 kcal')
    await next(user) // macros
    await next(user) // résumé

    expect(await screen.findByText('Vos objectifs quotidiens')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Terminer' }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/')
    })
  })

  it('permet de revenir en arrière', async () => {
    const user = userEvent.setup()
    stubOnboarding()
    renderRoute('/onboarding')

    await fillProfile(user)
    await next(user)
    expect(await screen.findByText(/Étape 2 sur 7/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Retour/ }))

    expect(await screen.findByText(/Étape 1 sur 7/)).toBeInTheDocument()
    // La saisie est conservée.
    expect(screen.getByLabelText('Taille')).toHaveValue(180)
  })

  it('conserve le brouillon dans sessionStorage', async () => {
    const user = userEvent.setup()
    stubOnboarding()
    renderRoute('/onboarding')

    await fillProfile(user)

    await waitFor(() => {
      const draft = window.sessionStorage.getItem('mfp-onboarding-draft')
      expect(draft).toContain('180')
    })
  })
})
