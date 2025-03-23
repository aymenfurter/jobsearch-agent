interface JobSectionProps {
  title: string;
  content?: string;
}

export const JobSection = ({ title, content }: JobSectionProps): JSX.Element | null => {
  if (!content) return null;
  
  return (
    <div className="job-section">
      <h3 className="computer-text text-lg font-medium mb-2">{title}</h3>
      <div 
        className="prose prose-sm max-w-none"
        dangerouslySetInnerHTML={{ __html: content }}
      />
    </div>
  );
};
