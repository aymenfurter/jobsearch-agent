import { useState, FormEvent } from 'react';
import { SearchFormData } from '@/types/state';

export function useSearchForm(onSubmit: (data: SearchFormData) => void) {
    const [query, setQuery] = useState('');
    const [country, setCountry] = useState('');

    const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!query.trim()) return;
        
        onSubmit({
            query: query.trim(),
            country: country.trim() || ''
        });
    };

    return {
        query,
        setQuery,
        country,
        setCountry,
        handleSubmit
    };
}
