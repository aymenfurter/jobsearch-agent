import os
import json
import requests
from typing import Any, Dict, Optional
from opentelemetry import trace

# For sending SMS
from azure.communication.sms import SmsClient

# Get the tracer
tracer = trace.get_tracer(__name__)

def search_jobs(query: str, country: Optional[str] = None) -> str:
    """
    Searches Microsoft job postings via an open API call.
    Returns a JSON string with the jobs that match the query (optionally filtered by country).
    """
    # Create a span for tracking the job search operation
    with tracer.start_as_current_span("search_jobs") as span:
        span.set_attribute("query", query)
        if country:
            span.set_attribute("country", country)
        
        base_url = "https://gcsservices.careers.microsoft.com/search/api/v1/search"
        params = {
            "q": query,        # e.g. "cloud solution architect"
            "l": "en_us",      # language
            "pg": 1,
            "pgSz": 20,
            "o": "Relevance",
            "flt": "true"
        }
        
        # If the user specified a country, add the 'lc' parameter
        if country:
            params["lc"] = country  # e.g., "Switzerland"

        try:
            # Record API call start time
            span.add_event("api_call_start")
            response = requests.get(base_url, params=params)
            span.add_event("api_call_end")
            
            # Add HTTP status code to span
            span.set_attribute("http.status_code", response.status_code)
            
            response.raise_for_status()
            data = response.json()
            
            # Add result metrics to span
            if "totalCount" in data:
                span.set_attribute("result_count", data["totalCount"])
            
            return json.dumps(data, ensure_ascii=False)
        except Exception as e:
            # Record the error in the span
            span.record_exception(e)
            span.set_attribute("error", str(e))
            return json.dumps({"error": str(e)})


def send_job_info_sms(job_id: str, job_title: str, phone_number: str) -> str:
    """
    Sends an SMS containing job ID and Title to the specified phone number 
    using Azure Communication Services.
    """
    with tracer.start_as_current_span("send_job_info_sms") as span:
        span.set_attribute("job_id", job_id)
        span.set_attribute("job_title", job_title)
        # Mask phone number for privacy in traces
        masked_number = f"{phone_number[:4]}****{phone_number[-4:]}" if len(phone_number) >= 8 else "****"
        span.set_attribute("phone_number", masked_number)
        
        try:
            sms_connection_str = os.environ.get("SMS_CONNECTION_STRING", "")
            if not sms_connection_str:
                error_msg = "Missing SMS_CONNECTION_STRING environment variable."
                span.set_attribute("error", error_msg)
                return json.dumps({"error": error_msg})

            sms_client = SmsClient.from_connection_string(sms_connection_str)

            sender = os.environ.get("PHONE_NUMBER", "")

            message_body = f"Job Info:\nID: {job_id}\nTitle: {job_title}"
            span.set_attribute("message_length", len(message_body))

            span.add_event("sms_send_start")
            sms_responses = sms_client.send(
                from_=sender,  # e.g. "+1425XXXXXXX"
                to=phone_number,                  # e.g. "+1415XXXXXXX"
                message=message_body,
                enable_delivery_report=True, 
                tag="job-info"
            )
            span.add_event("sms_send_complete")
            
            # The send call returns a collection of SmsSendResult objects
            for r in sms_responses:
                if r.successful:
                    span.set_attribute("sms_status", "successful")
                    return json.dumps({"message": "SMS successfully sent!", "jobId": job_id})
                else:
                    error_msg = f"Failed to send SMS: {r.http_status_code}"
                    span.set_attribute("sms_status", "failed")
                    span.set_attribute("http_status_code", r.http_status_code)
                    span.set_attribute("error", error_msg)
                    return json.dumps({"error": error_msg})
        except Exception as ex:
            span.record_exception(ex)
            span.set_attribute("error", str(ex))
            return json.dumps({"error": str(ex)})
