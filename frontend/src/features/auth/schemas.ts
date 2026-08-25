import { z } from 'zod'

/**
 * Schémas de validation des formulaires de compte.
 *
 * Ils doublent la validation du backend pour un retour immédiat : le serveur
 * reste la seule autorité (spec 05 §1).
 */

const username = z
  .string()
  .trim()
  .min(3, 'Le nom d’utilisateur doit contenir au moins 3 caractères.')
  .max(30, 'Le nom d’utilisateur ne peut pas dépasser 30 caractères.')
  .regex(/^[\w.@+-]+$/, 'Seuls les lettres, chiffres et les caractères . @ + - _ sont autorisés.')

const password = z.string().min(8, 'Le mot de passe doit contenir au moins 8 caractères.')

const optionalEmail = z.union([z.literal(''), z.email('Adresse email invalide.')]).optional()

export const loginSchema = z.object({
  username: z.string().trim().min(1, 'Le nom d’utilisateur est obligatoire.'),
  password: z.string().min(1, 'Le mot de passe est obligatoire.'),
})
export type LoginValues = z.infer<typeof loginSchema>

export const registrationSchema = z
  .object({
    first_name: z.string().trim().min(1, 'Le prénom est obligatoire.'),
    last_name: z.string().trim().min(1, 'Le nom est obligatoire.'),
    username,
    email: optionalEmail,
    password,
    password_confirmation: z.string(),
  })
  .refine((values) => values.password === values.password_confirmation, {
    message: 'Les deux mots de passe ne correspondent pas.',
    path: ['password_confirmation'],
  })
export type RegistrationValues = z.infer<typeof registrationSchema>

export const forgotPasswordSchema = z.object({
  username: z.string().trim().min(1, 'Le nom d’utilisateur est obligatoire.'),
})
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>

export const resetPasswordSchema = z
  .object({
    new_password: password,
    new_password_confirmation: z.string(),
  })
  .refine((values) => values.new_password === values.new_password_confirmation, {
    message: 'Les deux mots de passe ne correspondent pas.',
    path: ['new_password_confirmation'],
  })
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Le mot de passe actuel est obligatoire.'),
    new_password: password,
    new_password_confirmation: z.string(),
  })
  .refine((values) => values.new_password === values.new_password_confirmation, {
    message: 'Les deux mots de passe ne correspondent pas.',
    path: ['new_password_confirmation'],
  })
export type ChangePasswordValues = z.infer<typeof changePasswordSchema>

export const profileSchema = z.object({
  first_name: z.string().trim().min(1, 'Le prénom est obligatoire.'),
  last_name: z.string().trim().min(1, 'Le nom est obligatoire.'),
  username,
  email: optionalEmail,
})
export type ProfileValues = z.infer<typeof profileSchema>
