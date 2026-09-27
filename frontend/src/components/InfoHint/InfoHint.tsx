import {
    useId,
    useLayoutEffect,
    useRef,
    useState,
    type CSSProperties,
} from 'react';
import { createPortal } from 'react-dom';

import styles from './InfoHint.module.scss';

interface InfoHintProps {
    title: string;
    description: string;
    usage: string;
    className?: string;
}

interface TooltipPosition {
    left: number;
    top: number;
}

interface TooltipTheme {
    surface: string;
    borderHover: string;
    text: string;
    textStrong: string;
    popoverShadow: string;
}

const VIEWPORT_GAP = 12;
const TOOLTIP_GAP = 9;

export default function InfoHint({
    title,
    description,
    usage,
    className,
}: InfoHintProps) {
    const tooltipId = useId();
    const triggerRef = useRef<HTMLButtonElement>(null);
    const tooltipRef = useRef<HTMLDivElement>(null);
    const [visible, setVisible] = useState(false);
    const [position, setPosition] = useState<TooltipPosition>({ left: VIEWPORT_GAP, top: VIEWPORT_GAP });
    const [theme, setTheme] = useState<TooltipTheme>({
        surface: '',
        borderHover: '',
        text: '',
        textStrong: '',
        popoverShadow: '',
    });

    const positionTooltip = () => {
        const trigger = triggerRef.current;
        if (!trigger) return;

        const bounds = trigger.getBoundingClientRect();
        const computedStyle = window.getComputedStyle(trigger);
        const expectedWidth = Math.min(360, window.innerWidth - VIEWPORT_GAP * 2);
        setTheme({
            surface: computedStyle.getPropertyValue('--surface'),
            borderHover: computedStyle.getPropertyValue('--border-hover'),
            text: computedStyle.getPropertyValue('--text'),
            textStrong: computedStyle.getPropertyValue('--text-strong'),
            popoverShadow: computedStyle.getPropertyValue('--popover-shadow'),
        });
        setPosition({
            left: Math.min(
                window.innerWidth - expectedWidth - VIEWPORT_GAP,
                Math.max(VIEWPORT_GAP, bounds.left + bounds.width / 2 - expectedWidth / 2),
            ),
            top: bounds.bottom + TOOLTIP_GAP,
        });
        setVisible(true);
    };

    useLayoutEffect(() => {
        if (!visible || !tooltipRef.current || !triggerRef.current) return;

        const tooltipBounds = tooltipRef.current.getBoundingClientRect();
        const triggerBounds = triggerRef.current.getBoundingClientRect();
        const nextTop = tooltipBounds.bottom > window.innerHeight - VIEWPORT_GAP
            ? Math.max(VIEWPORT_GAP, triggerBounds.top - tooltipBounds.height - TOOLTIP_GAP)
            : position.top;
        const nextLeft = Math.min(
            window.innerWidth - tooltipBounds.width - VIEWPORT_GAP,
            Math.max(VIEWPORT_GAP, position.left),
        );

        if (nextTop !== position.top || nextLeft !== position.left) {
            setPosition({ left: nextLeft, top: nextTop });
        }
    }, [position.left, position.top, visible]);

    const tooltipStyle = {
        left: position.left,
        top: position.top,
        '--surface': theme.surface,
        '--border-hover': theme.borderHover,
        '--text': theme.text,
        '--text-strong': theme.textStrong,
        '--popover-shadow': theme.popoverShadow,
    } as CSSProperties;

    return (
        <span
            className={`${styles.hint} ${className ?? ''}`}
            onMouseEnter={positionTooltip}
            onMouseLeave={() => setVisible(false)}
        >
            <button
                ref={triggerRef}
                type="button"
                className={styles.trigger}
                aria-label={`Справка: ${title}`}
                aria-describedby={visible ? tooltipId : undefined}
                onFocus={positionTooltip}
                onBlur={() => setVisible(false)}
            >
                i
            </button>
            {visible && createPortal(
                <div
                    ref={tooltipRef}
                    id={tooltipId}
                    role="tooltip"
                    className={styles.tooltip}
                    style={tooltipStyle}
                >
                    <strong className={styles.title}>{title}</strong>
                    <div className={styles.section}>
                        <b>Что показывает</b>
                        <p>{description}</p>
                    </div>
                    <div className={styles.section}>
                        <b>Как пользоваться</b>
                        <p>{usage}</p>
                    </div>
                </div>,
                document.body,
            )}
        </span>
    );
}
