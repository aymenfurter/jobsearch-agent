import { Job } from "@/types";
import { MapPin, Calendar, Building } from "lucide-react";

interface JobDetailsProps {
    job: Job;
}

export function JobDetails({ job }: JobDetailsProps) {
    return (
        <div className="space-y-6">
            <div className="border-b border-primary/30 pb-4">
                <h2 className="computer-text text-xl mb-4">{job.title}</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="flex items-center text-sm text-muted-foreground">
                        <MapPin className="h-4 w-4 mr-2" />
                        {job.primaryWorkLocation.city}, {job.primaryWorkLocation.state}
                    </div>
                    <div className="flex items-center text-sm text-muted-foreground">
                        <Calendar className="h-4 w-4 mr-2" />
                        Posted: {new Date(job.posted.external).toLocaleDateString()}
                    </div>
                    <div className="flex items-center text-sm text-muted-foreground">
                        <Building className="h-4 w-4 mr-2" />
                        {job.workSiteFlexibility}
                    </div>
                </div>
            </div>

            <div className="space-y-6">
                <section>
                    <h3 className="computer-text text-lg mb-3">DESCRIPTION</h3>
                    <div 
                        className="prose prose-invert max-w-none"
                        dangerouslySetInnerHTML={{ __html: job.description }} 
                    />
                </section>

                <section>
                    <h3 className="computer-text text-lg mb-3">QUALIFICATIONS</h3>
                    <div 
                        className="prose prose-invert max-w-none"
                        dangerouslySetInnerHTML={{ __html: job.qualifications }} 
                    />
                </section>

                <section>
                    <h3 className="computer-text text-lg mb-3">RESPONSIBILITIES</h3>
                    <div 
                        className="prose prose-invert max-w-none"
                        dangerouslySetInnerHTML={{ __html: job.responsibilities }} 
                    />
                </section>
            </div>
        </div>
    );
}
