import { ExternalLink } from "lucide-react";
import { Button } from "./button";
import { Job } from "@/types";

interface SearchResultsProps {
  results: Job[];
  totalCount: number;
  onSelectJob: (jobId: string) => void;
}

export function SearchResults({ results, totalCount, onSelectJob }: SearchResultsProps) {
  if (!results || results.length === 0) {
    return (
      <div className="text-center p-4">
        <h2 className="computer-text text-2xl">No Search Results</h2>
        <p className="text-muted-foreground mt-2">Please try a different search query.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="computer-text text-2xl">Search Results</h2>
        <span className="text-sm text-muted-foreground">{totalCount} total matches</span>
      </div>

      <div className="space-y-4">
        {results.map((job) => (
          <div key={job.jobId} className="border border-primary/20 rounded-md p-4 bg-background/50 hover:bg-background/80 transition-colors">
            <div className="flex justify-between items-start mb-2">
              <h3 className="computer-text text-lg font-medium">{job.title}</h3>
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-8"
                  onClick={() => onSelectJob(job.jobId)}
                >
                  VIEW DETAILS
                </Button>
                {'jobUrl' in job && job.jobUrl && (
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8" 
                    onClick={() => window.open(job.jobUrl, '_blank')}
                  >
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex text-sm text-muted-foreground">
                <span className="mr-2">ID: {job.jobId}</span>
                {job.properties?.primaryLocation && <span>• {job.properties?.primaryLocation}</span>}
                {job.properties?.employmentType && <span>• {job.properties?.employmentType}</span>}
              </div>
              {job.description && (
                <p className="text-sm line-clamp-2">{job.description}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
