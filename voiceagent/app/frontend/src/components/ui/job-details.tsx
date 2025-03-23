// UI Component imports
import { Button } from "./button";
import { JobSection } from "./job-section";

// Icon imports
import { ArrowLeft } from "lucide-react";

// Type imports
import { Job } from "@/types";

interface JobDetailsProps {
  job: Job;
  onBackToResults: () => void;
}

interface JobMetadataProps {
  jobId: string;
  location?: string;
  employmentType?: string;
}

const JobMetadata = ({ jobId, location, employmentType }: JobMetadataProps): JSX.Element => (
  <div className="text-sm text-muted-foreground mt-2 flex flex-wrap gap-x-3 gap-y-1">
    <span>ID: {jobId}</span>
    {location && <span>• {location}</span>}
    {employmentType && <span>• {employmentType}</span>}
  </div>
);

export function JobDetails({ job, onBackToResults }: JobDetailsProps): JSX.Element {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={onBackToResults}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <h2 className="computer-text text-2xl">JOB DETAILS</h2>
        </div>
      </div>

      <div className="border border-primary/20 rounded-md p-6 space-y-6 bg-background/50">
        <div>
          <h1 className="computer-text text-2xl font-bold">{job.title}</h1>
          <JobMetadata 
            jobId={job.jobId}
            location={'primaryLocation' in job ? job.primaryLocation : undefined}
            employmentType={'employmentType' in job ? job.employmentType : undefined}
          />
        </div>

        <JobSection title="DESCRIPTION" content={job.description} />
        <JobSection title="QUALIFICATIONS" content={job.qualifications} />
        <JobSection title="RESPONSIBILITIES" content={job.responsibilities} />
      </div>
    </div>
  );
}
