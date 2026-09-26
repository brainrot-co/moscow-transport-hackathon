import { useEffect, useState } from 'react'

const THEME_STORAGE_KEY = 'dashboard-theme'

export default function useTheme() {
    const [isLightTheme, setIsLightTheme] = useState(
        () => window.localStorage.getItem(THEME_STORAGE_KEY) !== 'dark',
    )

    useEffect(() => {
        const theme = isLightTheme ? 'light' : 'dark'

        window.localStorage.setItem(THEME_STORAGE_KEY, theme)
        document.documentElement.dataset.theme = theme
        document.documentElement.style.colorScheme = theme
    }, [isLightTheme])

    return { isLightTheme, setIsLightTheme }
}
