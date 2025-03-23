import { MapPin } from "lucide-react";
import { Button } from "./button";

interface SearchResultsProps {
    results: any[];
    totalCount: number;
}

export function SearchResults({ results, totalCount }: SearchResultsProps) {
    return (
        <div className="space-y-6">
            <h2 className="computer-text text-xl">SEARCH RESULTS ({totalCount} JOBS FOUND)</h2>
            <div className="grid grid-cols-1 gap-4">
                {results.map((job) => (
                    <div 
                        key={job.jobId}
                        className="p-4 border border-primary/30 rounded-lg hover:border-primary/60 transition-colors"
                    >
                        <h3 className="computer-text text-lg mb-2">{job.title}</h3>
                        <div className="flex items-center text-sm text-muted-foreground mb-4">
                            <MapPin className="h-4 w-4 mr-2" />
                            {job.properties.primaryLocation}
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-muted-foreground">
                                {job.properties.workSiteFlexibility}
                            </span>
                            <Button 
                                onClick={() => window.selectJob(job.jobId)}
                                variant="outline"
                                size="sm"
                            >
                                VIEW DETAILS
                            </Button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
