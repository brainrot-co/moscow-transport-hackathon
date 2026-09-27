import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';

type StateValidator<T> = (value: unknown) => value is T;

export default function usePersistentState<T>(
    storageKey: string,
    initialValue: T,
    isValid: StateValidator<T>,
): [T, Dispatch<SetStateAction<T>>] {
    const [value, setValue] = useState<T>(() => {
        try {
            const storedValue = window.localStorage.getItem(storageKey);
            if (storedValue === null) return initialValue;

            const parsedValue: unknown = JSON.parse(storedValue);
            return isValid(parsedValue) ? parsedValue : initialValue;
        } catch {
            return initialValue;
        }
    });

    useEffect(() => {
        try {
            window.localStorage.setItem(storageKey, JSON.stringify(value));
        } catch {
            // Интерфейс продолжает работать, даже если хранилище браузера недоступно.
        }
    }, [storageKey, value]);

    return [value, setValue];
}
