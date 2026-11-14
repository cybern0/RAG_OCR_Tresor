/** Assemble des noms de classes en ignorant les valeurs vides. */
export const cn = (...parts: Array<string | false | null | undefined>) => parts.filter(Boolean).join(' ')
