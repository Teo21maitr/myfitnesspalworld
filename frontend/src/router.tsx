import { createBrowserRouter } from 'react-router-dom'

import { AppLayout } from '@/components/layout/app-layout'
import { AuthLayout } from '@/components/layout/auth-layout'
import {
  RedirectIfAuthenticated,
  RedirectIfOnboarded,
  RequireAuth,
  RequireOnboarding,
} from '@/features/auth/require-auth'
import { AccountPage } from '@/pages/account-page'
import { EditFoodPage } from '@/pages/foods/edit-food-page'
import { FoodDetailPage } from '@/pages/foods/food-detail-page'
import { FoodSearchPage } from '@/pages/foods/food-search-page'
import { QuickAddPage } from '@/pages/diary/quick-add-page'
import { LazyScannerPage } from '@/pages/foods/lazy-scanner-page'
import { MyFoodsPage } from '@/pages/foods/my-foods-page'
import { GoalsPage } from '@/pages/goals-page'
import { ForgotPasswordPage } from '@/pages/auth/forgot-password-page'
import { LoginPage } from '@/pages/auth/login-page'
import { RegisterRequestPage } from '@/pages/auth/register-request-page'
import { RegistrationSentPage } from '@/pages/auth/registration-sent-page'
import { ResetPasswordPage } from '@/pages/auth/reset-password-page'
import { HomePage } from '@/pages/home-page'
import { JournalPage } from '@/pages/journal-page'
import { NotFoundPage } from '@/pages/not-found-page'
import { OnboardingPage } from '@/pages/onboarding-page'
import { ProgressPage } from '@/pages/progress-page'
import { EditRecipePage } from '@/pages/recipes/edit-recipe-page'
import { NewRecipePage } from '@/pages/recipes/new-recipe-page'
import { RecipeDetailPage } from '@/pages/recipes/recipe-detail-page'
import { RecipesPage } from '@/pages/recipes/recipes-page'
import { SavedMealsPage } from '@/pages/saved-meals-page'
import { FriendsPage } from '@/pages/friends-page'
import { SharedDiaryPage } from '@/pages/shared/shared-diary-page'
import { SharedProgressPage } from '@/pages/shared/shared-progress-page'
import { SharesPage } from '@/pages/shares-page'

export const routes = [
  {
    // Écrans publics : un utilisateur déjà connecté est renvoyé à l'accueil.
    element: (
      <RedirectIfAuthenticated>
        <AuthLayout />
      </RedirectIfAuthenticated>
    ),
    children: [
      { path: '/connexion', element: <LoginPage /> },
      { path: '/demande-inscription', element: <RegisterRequestPage /> },
      { path: '/mot-de-passe-oublie', element: <ForgotPasswordPage /> },
    ],
  },
  {
    // Écrans publics accessibles même connecté.
    element: <AuthLayout />,
    children: [
      { path: '/demande-envoyee', element: <RegistrationSentPage /> },
      { path: '/reinitialiser-mot-de-passe', element: <ResetPasswordPage /> },
    ],
  },
  {
    // Parcours d'onboarding : authentifié, mais hors de l'application tant
    // qu'il n'est pas terminé.
    path: '/onboarding',
    element: (
      <RequireAuth>
        <RedirectIfOnboarded>
          <AuthLayout />
        </RedirectIfOnboarded>
      </RequireAuth>
    ),
    children: [{ index: true, element: <OnboardingPage /> }],
  },
  {
    path: '/',
    element: (
      <RequireAuth>
        <RequireOnboarding>
          <AppLayout />
        </RequireOnboarding>
      </RequireAuth>
    ),
    children: [
      { index: true, element: <HomePage /> },
      { path: 'journal', element: <JournalPage /> },
      { path: 'aliments', element: <FoodSearchPage /> },
      { path: 'aliments/:id', element: <FoodDetailPage /> },
      { path: 'mes-aliments', element: <MyFoodsPage /> },
      { path: 'mes-aliments/:id', element: <EditFoodPage /> },
      { path: 'scanner', element: <LazyScannerPage /> },
      { path: 'ajout-rapide', element: <QuickAddPage /> },
      { path: 'recettes', element: <RecipesPage /> },
      { path: 'recettes/nouvelle', element: <NewRecipePage /> },
      { path: 'recettes/:id', element: <RecipeDetailPage /> },
      { path: 'recettes/:id/modifier', element: <EditRecipePage /> },
      { path: 'mes-repas', element: <SavedMealsPage /> },
      { path: 'progression', element: <ProgressPage /> },
      { path: 'amis', element: <FriendsPage /> },
      { path: 'amis/:userId/journal', element: <SharedDiaryPage /> },
      { path: 'amis/:userId/progression', element: <SharedProgressPage /> },
      { path: 'partages', element: <SharesPage /> },
      { path: 'objectifs', element: <GoalsPage /> },
      { path: 'compte', element: <AccountPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
