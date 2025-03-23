import { Job } from "@/types";

export interface UIState {
    search: {
        query: string | null;
        country: string | null;
        results: any[] | null;
        total_count: number;
    };
    current_job: Job | null;
    view_mode: 'search' | 'detail';
}

export interface SearchFormData {
    query: string;
    country: string;
}
