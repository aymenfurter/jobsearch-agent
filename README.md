# Load Balancing for Azure OpenAI Realtime API Calls

## Overview

Realtime API calls are inherently "sticky" - the WebSocket connections remain open once established. The most effective approach within Azure API Management (APIM) is to round-robin distribute new connection requests.

## Implementation Details

This repository demonstrates how APIM can be used to load balance across different Azure OpenAI models and endpoints. The implementation is inspired by the [AI Hub Gateway Solution Accelerator](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator), which includes configuration for the Azure OpenAI Realtime API.

The load balancing policy in this repository (`load_balancing_policy.xml`) distributes incoming WebSocket connections across multiple Azure OpenAI endpoints to achieve greater total throughput.

## How It Works

The policy uses a hashing algorithm based on the request ID to deterministically route new connections to one of the available backends:

1. Each incoming request is assigned a hash value based on the request ID
2. The request is directed to one of the available Azure OpenAI endpoints based on this hash
3. Backend-specific configuration (endpoint URI and API key) is applied
4. The connection is established to the selected backend

## Considerations

- This approach balances the number of new socket connections rather than the workload itself
- Client-side load balancing is an alternative approach that may be suitable for some scenarios
- For maximum effectiveness, consider combining this with other scaling strategies

## Implementation Example

See the `load_balancing_policy.xml` file for the complete APIM policy implementation.