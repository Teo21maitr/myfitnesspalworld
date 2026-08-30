/**
 * Ce que chaque écran de l'application permet de faire.
 *
 * Le guide ne recopie pas la liste des destinations : il la **complète**. La
 * page se construit à partir de `NAV_SECTIONS`, et ce fichier n'apporte que
 * les phrases. Une fonctionnalité ajoutée au menu apparaît donc dans le guide
 * sans qu'on y pense — et un test échoue si sa description manque, plutôt que
 * de la laisser sortir muette.
 *
 * Le ton s'adresse à quelqu'un qui découvre : à quoi ça sert, pas comment
 * c'est fait.
 */

/** Description d'un écran, indexée par sa route. */
export const GUIDE_DESCRIPTIONS: Record<string, string> = {
  '/': 'Ta journée d’un coup d’œil : ce que tu as mangé, ce qu’il te reste, et où en est ton poids.',
  '/journal':
    'Le détail de tes repas, jour par jour. Tu peux revenir sur hier, préparer demain, et déplacer un aliment d’un repas à l’autre.',
  '/ajout-rapide':
    'Quand tu connais les calories mais pas l’aliment — au restaurant, chez des amis. Tu notes un chiffre, c’est tout.',

  '/aliments':
    'La recherche. Elle couvre les aliments de la table officielle française, les produits de marque et ceux que tu as créés.',
  '/mes-aliments':
    'Tes propres fiches, pour ce que la base ne connaît pas : une recette de famille, un produit local.',
  '/scanner': 'Vise le code-barres d’un produit avec ton appareil photo : sa fiche s’ouvre.',
  '/scanner-repas':
    'Photographie ton assiette. L’application propose les aliments qu’elle reconnaît ; tu corriges avant d’enregistrer — elle se trompe, et c’est prévu.',
  '/scanner-etiquette':
    'Photographie le tableau nutritionnel au dos d’un produit : le formulaire de création se remplit tout seul.',

  '/recettes':
    'Tes plats et leurs ingrédients. L’application calcule les valeurs pour une portion, et tu ajoutes le nombre de portions mangées.',
  '/mes-repas':
    'Des assemblages que tu réutilises. Ton petit-déjeuner habituel devient un seul ajout au lieu de cinq.',
  '/planification': 'Compose tes menus à l’avance, sur un jour ou sur la semaine.',
  '/courses':
    'La liste des ingrédients, regroupés par aliment, à partir d’un planning ou de recettes. Tu coches en faisant les courses.',

  '/progression':
    'Ton poids et tes mensurations, avec leur courbe et la tendance sur les dernières semaines.',
  '/photos':
    'Des photos datées pour voir l’évolution. Elles restent privées : elles ne se partagent avec personne, jamais.',
  '/objectifs':
    'Tes calories et tes macronutriments visés. Calculés à l’inscription, modifiables quand tu veux.',
  '/analyse':
    'D’où viennent tes protéines, tes fibres, ton sucre. Utile pour comprendre ce qui pèse dans une journée.',
  '/rapports':
    'Un résumé sur la période de ton choix — moyennes, poids, aliments principaux — à télécharger en PDF ou en tableur.',

  '/amis': 'Cherche quelqu’un par son nom d’utilisateur, envoie-lui une demande.',
  '/partages':
    'Ce que tes amis peuvent voir : une recette, une liste de courses, ton journal, ta progression. Chaque partage se retire quand tu veux.',

  '/notifications': 'Les messages de l’application, et tes rappels — repas, pesée.',
  '/compte': 'Ton profil, ton mot de passe, le thème clair ou sombre.',
  '/guide': 'Cette page.',
}

/** Un ordre d'usage, pour qui vient d'arriver. */
export interface GuideStep {
  to: string
  title: string
  body: string
}

/**
 * Les trois gestes du quotidien.
 *
 * Vingt-deux fonctionnalités listées n'apprennent pas à s'en servir : il faut
 * dire par quoi commencer.
 */
export const GUIDE_STEPS: GuideStep[] = [
  {
    to: '/objectifs',
    title: 'Fixe ton objectif',
    body: 'Ton poids actuel, celui que tu vises et le rythme voulu suffisent : l’application en déduit tes calories et tes macros. C’est une estimation, pas une prescription médicale.',
  },
  {
    to: '/journal',
    title: 'Note ce que tu manges',
    body: 'Cherche l’aliment, scanne un code-barres ou photographie ton assiette. L’essentiel est la régularité, pas la précision au gramme.',
  },
  {
    to: '/progression',
    title: 'Suis ton évolution',
    body: 'Pèse-toi régulièrement, au même moment de la journée. La courbe compte davantage qu’une pesée isolée.',
  },
]
