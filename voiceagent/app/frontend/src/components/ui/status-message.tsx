import { AlertCircle, Search } from "lucide-react";
import "./status-message.css";

type Properties = {
    isRecording: boolean;
};

export default function StatusMessage({ isRecording }: Properties) {
    if (!isRecording) {
        return (
            <div className="flex items-center text-muted-foreground">
                <AlertCircle className="mr-2 h-4 w-4" />
                <span className="text-sm">
                    ASK ME ABOUT JOB OPPORTUNITIES AT MICROSOFT
                </span>
            </div>
        );
    }

    return (
        <div className="flex items-center text-primary">
            <Search className="mr-2 h-4 w-4 animate-pulse" />
            <span className="text-sm">LISTENING FOR JOB SEARCH QUERY</span>
        </div>
    );
}
