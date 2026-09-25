import styles from './ThemeToggle.module.scss'

interface ThemeToggleProps {
    isLightTheme: boolean
    onToggle: () => void
    className?: string
}

export default function ThemeToggle({ isLightTheme, onToggle, className = '' }: ThemeToggleProps) {
    return (
        <button
            type="button"
            role="switch"
            aria-checked={isLightTheme}
            aria-label={isLightTheme ? 'Включить тёмную тему' : 'Включить светлую тему'}
            className={`${styles.themeToggle} ${className}`}
            onClick={onToggle}
        >
            <svg viewBox="0 0 24 24" aria-hidden="true">
                {isLightTheme ? (
                    <path d="M20 15.2A8 8 0 0 1 8.8 4a8 8 0 1 0 11.2 11.2Z" />
                ) : (
                    <>
                        <circle cx="12" cy="12" r="3.5" />
                        <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
                    </>
                )}
            </svg>
            <span>{isLightTheme ? 'Тёмная тема' : 'Светлая тема'}</span>
        </button>
    )
}
