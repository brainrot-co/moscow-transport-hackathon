import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import logoRed from '../../assets/logo-red.svg'
import moscowCoatOfArms from '../../assets/moscow-coa.svg'
import padlockIcon from '../../assets/padlock.svg'
import userIcon from '../../assets/user.svg'
import viewIcon from '../../assets/view.svg'
import ThemeToggle from '../../components/ThemeToggle/ThemeToggle'
import useTheme from '../../hooks/useTheme'
import { login } from '../../api/auth'
import { ApiError, getAccessToken } from '../../api/client'

import styles from './Login.module.scss'

export default function Login() {
    const navigate = useNavigate()
    const [isPasswordVisible, setIsPasswordVisible] = useState(false)
    const demoUsername = import.meta.env.VITE_DEMO_USERNAME ?? ''
    const demoPassword = import.meta.env.VITE_DEMO_PASSWORD ?? ''
    const [username, setUsername] = useState(demoUsername)
    const [password, setPassword] = useState(demoPassword)
    const [remember, setRemember] = useState(true)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState('')
    const { isLightTheme, setIsLightTheme } = useTheme()

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        setSubmitting(true)
        setError('')
        try {
            await login(username, password, remember)
            navigate('/dashboard', { replace: true })
        } catch (requestError) {
            setError(
                requestError instanceof ApiError && requestError.status === 401
                    ? 'Неверный логин или пароль'
                    : 'Не удалось войти. Проверьте, запущен ли backend.',
            )
        } finally {
            setSubmitting(false)
        }
    }

    if (getAccessToken()) {
        return <Navigate to="/dashboard" replace />
    }

    return (
        <main className={`${styles.page} ${isLightTheme ? styles.lightTheme : ''}`}>
            <div className={styles.brand} aria-label="Московский транспорт">
                <img src={logoRed} alt="" />
                <span>Московский<br />транспорт</span>
            </div>

            <section className={styles.hero} aria-labelledby="login-hero-title">
                <h1 id="login-hero-title">Умный транспорт -<br />комфортный город</h1>
                <p>Анализируй. Планируй. Развивай.</p>
            </section>

            <section className={styles.loginCard} aria-labelledby="login-title">
                <ThemeToggle
                    isLightTheme={isLightTheme}
                    onToggle={() => setIsLightTheme((isLight) => !isLight)}
                    className={styles.themeControl}
                />
                <img className={styles.cardLogo} src={logoRed} alt="" />

                <div className={styles.intro}>
                    <h2 id="login-title">Добро пожаловать!</h2>
                    <p>Войдите в систему, чтобы продолжить</p>
                </div>

                <form className={styles.form} onSubmit={handleSubmit}>
                    <div className={styles.fieldGroup}>
                        <label htmlFor="login">Логин</label>
                        <div className={styles.inputWrapper}>
                            <img src={userIcon} alt="" />
                            <input
                                id="login"
                                name="login"
                                type="text"
                                placeholder="Введите ваш логин"
                                autoComplete="username"
                                value={username}
                                onChange={(event) => setUsername(event.target.value)}
                                required
                            />
                        </div>
                    </div>

                    <div className={styles.fieldGroup}>
                        <label htmlFor="password">Пароль</label>
                        <div className={styles.inputWrapper}>
                            <img src={padlockIcon} alt="" />
                            <input
                                id="password"
                                name="password"
                                type={isPasswordVisible ? 'text' : 'password'}
                                placeholder="Введите пароль"
                                autoComplete="current-password"
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                required
                            />
                            <button
                                className={styles.passwordToggle}
                                type="button"
                                aria-label={isPasswordVisible ? 'Скрыть пароль' : 'Показать пароль'}
                                aria-pressed={isPasswordVisible}
                                onClick={() => setIsPasswordVisible((isVisible) => !isVisible)}
                            >
                                <img src={viewIcon} alt="" />
                            </button>
                        </div>
                    </div>

                    <div className={styles.formOptions}>
                        <label className={styles.rememberMe}>
                            <input
                                name="remember"
                                type="checkbox"
                                checked={remember}
                                onChange={(event) => setRemember(event.target.checked)}
                            />
                            <span className={styles.checkbox} aria-hidden="true" />
                            <span>Запомнить меня</span>
                        </label>

                        <button className={styles.forgotPassword} type="button">
                            Забыли пароль?
                        </button>
                    </div>

                    {demoUsername && demoPassword && (
                        <p className={styles.demoCredentials}>
                            Демо-доступ: <b>{demoUsername}</b> / <b>{demoPassword}</b>
                        </p>
                    )}
                    {error && <p className={styles.loginError} role="alert">{error}</p>}

                    <button className={styles.submitButton} type="submit" disabled={submitting}>
                        <span>{submitting ? 'Входим…' : 'Войти'}</span>
                        <span aria-hidden="true">→</span>
                    </button>

                    <div className={styles.serviceInfo}>
                        <img src={moscowCoatOfArms} alt="Герб Москвы" />
                        <p>Сервис аналитики<br />Московского транспорта</p>
                    </div>
                </form>
            </section>
        </main>
    )
}
