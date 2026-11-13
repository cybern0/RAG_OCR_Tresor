// Bouton « Remplir avec exemple » : présent sur chaque formulaire de l'application, il remplit les champs avec de
// fausses informations (ils restent vides tant qu'on ne clique pas). Utile pour la démonstration et les essais.

export default function ExampleButton({ onFill, className = '' }: { onFill: () => void; className?: string }) {
  return (
    <button
      type="button"
      onClick={onFill}
      className={`text-xs font-medium text-gold-400 underline decoration-dotted underline-offset-4 hover:text-gold-300 ${className}`}
    >
      ✎ Remplir avec exemple
    </button>
  )
}
