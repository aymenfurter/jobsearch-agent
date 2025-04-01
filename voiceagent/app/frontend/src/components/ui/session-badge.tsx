import { UserCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SessionBadgeProps {
  sessionId: string;
  compact?: boolean;
  inline?: boolean;
  className?: string;
}

/**
 * SessionBadge displays the current user session ID in various formats
 * 
 * @param sessionId - The current session ID to display
 * @param compact - Display in compact mode (icon only with truncated ID)
 * @param inline - Display as an inline element for text content
 * @param className - Additional CSS classes
 */
export function SessionBadge({ 
  sessionId, 
  compact = false, 
  inline = false,
  className 
}: SessionBadgeProps) {
  // Truncate session ID for display
  const displayId = compact 
    ? sessionId.substring(0, 4) 
    : sessionId.substring(0, 8);

  // Tooltip shows full session ID on hover
  const tooltip = `Session ID: ${sessionId}`;
  
  if (inline) {
    return (
      <span 
        className={cn("text-primary/80 hover:text-primary transition-colors", className)}
        title={tooltip}
      >
        Session: {displayId}...
      </span>
    );
  }
  
  return (
    <div 
      className={cn(
        "flex items-center gap-1 px-2 py-1 bg-primary/10 border border-primary/20 rounded-md",
        compact ? "text-xs" : "text-sm",
        className
      )}
      title={tooltip}
    >
      <UserCircle className={compact ? "h-3 w-3" : "h-4 w-4"} />
      <span className="text-primary/80">
        {compact ? displayId : `Session: ${displayId}`}
        {!compact && "..."}
      </span>
    </div>
  );
}