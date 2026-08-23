import { createBrowserRouter } from 'react-router-dom'

import { AppLayout } from '@/components/layout/app-layout'
import { HomePage } from '@/pages/home-page'
import { JournalPage } from '@/pages/journal-page'
import { NotFoundPage } from '@/pages/not-found-page'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'journal', element: <JournalPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
