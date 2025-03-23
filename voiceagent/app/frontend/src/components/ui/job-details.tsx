import { ArrowLeft, ExternalLink } from "lucide-react";
import { Button } from "./button";
import { Job } from "@/types";

interface JobDetailsProps {
  job: Job;
  onBackToResults: () => void;
}

// Helper function to safely render HTML content
const createMarkup = (htmlContent: string) => {
  return { __html: htmlContent };
};

export function JobDetails({ job, onBackToResults }: JobDetailsProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={onBackToResults}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <h2 className="computer-text text-2xl">JOB DETAILS</h2>
        </div>
        {'jobUrl' in job && job.jobUrl && (
          <Button 
            variant="outline" 
            size="sm"
            className="flex items-center gap-2"
            onClick={() => window.open(job.jobUrl, '_blank')}
          >
            <span>APPLY ON MICROSOFT.COM</span>
            <ExternalLink className="h-4 w-4" />
          </Button>
        )}
      </div>

      <div className="border border-primary/20 rounded-md p-6 space-y-6 bg-background/50">
        <div>
          <h1 className="computer-text text-2xl font-bold">{job.title}</h1>
          <div className="text-sm text-muted-foreground mt-2 flex flex-wrap gap-x-3 gap-y-1">
            <span>ID: {job.jobId}</span>
            {'location' in job && job.primaryLocation && <span>• {job.primaryLocation}</span>}
            {'employmentType' in job && job.employmentType && <span>• {job.employmentType}</span>}
          </div>
        </div>

        {job.description && (
          <div>
            <h3 className="computer-text text-lg font-medium mb-2">DESCRIPTION</h3>
            <div 
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={createMarkup(job.description)}
            />
          </div>
        )}

        {job.qualifications && (
          <div>
            <h3 className="computer-text text-lg font-medium mb-2">QUALIFICATIONS</h3>
            <div 
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={createMarkup(job.qualifications)}
            />
          </div>
        )}
        
        {job.responsibilities && (
          <div>
            <h3 className="computer-text text-lg font-medium mb-2">RESPONSIBILITIES</h3>
            <div 
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={createMarkup(job.responsibilities)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
