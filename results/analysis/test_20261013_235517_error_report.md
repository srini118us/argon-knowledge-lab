# Error report: test_20261013_235517

## A / gemini-3.8-flash: 2 incorrect, 2 with a superseded citation
* **C03** (conflicting_versions) correct, but cites a superseded version. Q: What rate limit does the SwiftShip contract allow?  
  Status: answered. Answer: Under the current contract (CT-SWIFT-2024 Amendment 1), the SwiftShip API rate limit allows 120 requests per second across Northwind Logistics' account as a whole (raised from the original agreement's limit of 50 requests per second).  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']
* **C04** (conflicting_versions) correct, but cites a superseded version. Q: Can SwiftShip support be reached at 23:00 Eastern Time?  
  Status: answered. Answer: Yes. Although SwiftShip support was previously limited to 06:00 to 22:00 Eastern Time under the original agreement, Amendment 1 made vendor support available 24x7, meaning support can be reached at any time of day, including 23:00 Eastern Time.  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']
* **C05** (conflicting_versions) INCORRECT. Q: What timeout should payment-service use for PayNimbus calls?  
  Status: answered. Answer: payment-service should use an 8 second timeout for every PayNimbus call, which covers the full request from sending to receiving a complete response.  
  Cited: ['SPEC-PAY-INT@v2']. Required: ['SPEC-PAY-INT@v2']. Superseded: ['SPEC-PAY-INT@v1']
* **D01** (diagram) INCORRECT. Q: Does payment-service call PayNimbus synchronously or asynchronously?  
  Status: not_found. Answer: The available documentation does not state whether payment-service calls PayNimbus synchronously or asynchronously.  
  Cited: []. Required: ['DIAG-01@v1']. Superseded: []

## A / gemini-4-argon: 1 incorrect, 3 with a superseded citation
* **C01** (conflicting_versions) correct, but cites a superseded version. Q: Which message broker does Orion use as its event bus today?  
  Status: answered. Answer: Orion uses Apache Kafka as its event bus today, having migrated from RabbitMQ (which was previously selected in ADR-003@v1 and superseded by ADR-019@v1).  
  Cited: ['ADR-019@v1', 'ADR-003@v1', 'CAT-SERVICES@2025', 'POL-DR-02@v1']. Required: ['ADR-019@v1']. Superseded: ['ADR-003@v1']
* **C03** (conflicting_versions) correct, but cites a superseded version. Q: What rate limit does the SwiftShip contract allow?  
  Status: answered. Answer: The current SwiftShip contract (Amendment 1) allows an API rate limit of 120 requests per second across Northwind Logistics' account as a whole, raising it from the original limit of 50 requests per second.  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']
* **C04** (conflicting_versions) correct, but cites a superseded version. Q: Can SwiftShip support be reached at 23:00 Eastern Time?  
  Status: answered. Answer: Yes. Under Amendment 1 of the SwiftShip agreement (CT-SWIFT-2024@A1), SwiftShip vendor support is available 24x7 (replacing the previous 06:00 to 22:00 Eastern Time hours in CT-SWIFT-2024@v1).  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']
* **C05** (conflicting_versions) INCORRECT. Q: What timeout should payment-service use for PayNimbus calls?  
  Status: answered. Answer: payment-service should use an 8 second timeout for every PayNimbus call, covering the full request from sending to receiving a complete response (reduced from 10 seconds in v1 to align with the PayNimbus contractual p99 response guarantee).  
  Cited: ['SPEC-PAY-INT@v2']. Required: ['SPEC-PAY-INT@v2']. Superseded: ['SPEC-PAY-INT@v1']

## L / gemini-3.8-flash: 0 incorrect, 0 with a superseded citation

## L / gemini-4-argon: 0 incorrect, 3 with a superseded citation
* **C01** (conflicting_versions) correct, but cites a superseded version. Q: Which message broker does Orion use as its event bus today?  
  Status: answered. Answer: Orion uses Apache Kafka as its event bus today, having migrated from RabbitMQ.  
  Cited: ['ADR-019@v1', 'ADR-003@v1']. Required: ['ADR-019@v1']. Superseded: ['ADR-003@v1']
* **C03** (conflicting_versions) correct, but cites a superseded version. Q: What rate limit does the SwiftShip contract allow?  
  Status: answered. Answer: Under Amendment 1 of the SwiftShip agreement (CT-SWIFT-2024@A1), the contracted rate limit for the SwiftShip API is 120 requests per second across Northwind Logistics' account as a whole (raised from the original 50 requests per second in CT-SWIFT-2024@v1). Note that ADR-024@v1 caps carrier-gateway'  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1', 'ADR-024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']
* **C04** (conflicting_versions) correct, but cites a superseded version. Q: Can SwiftShip support be reached at 23:00 Eastern Time?  
  Status: answered. Answer: Yes. Under Amendment 1 to the SwiftShip agreement, vendor support is available 24x7 (replacing the previous 06:00 to 22:00 Eastern Time hours in the original agreement), so support requests may be raised at any time of day, on any day.  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']

## R1 / gemini-3.8-flash: 9 incorrect, 1 with a superseded citation
* **X07** (cross_document) INCORRECT. Q: How must payment-service authenticate when it calls inventory-service?  
  Status: answered. Answer: When calling inventory-service, payment-service must authenticate using OAuth2 client credentials issued by identity-service. It must obtain an access token using the client credentials grant and present it as a bearer token on the request; there are no exemptions for this path.  
  Cited: ['ADR-011@v1']. Required: ['ADR-011@v1', 'POL-SEC-01@v2']. Superseded: ['POL-SEC-01@v1']
* **C03** (conflicting_versions) correct, but cites a superseded version. Q: What rate limit does the SwiftShip contract allow?  
  Status: answered. Answer: Under Amendment 1 of the SwiftShip carrier services agreement, the contracted API rate limit for Northwind Logistics is 120 requests per second across the account as a whole (raised from the original 50 requests per second).  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']
* **D01** (diagram) INCORRECT. Q: Does payment-service call PayNimbus synchronously or asynchronously?  
  Status: not_found. Answer: The provided documentation does not specify whether payment-service calls PayNimbus synchronously or asynchronously.  
  Cited: []. Required: ['DIAG-01@v1']. Superseded: []
* **D02** (diagram) INCORRECT. Q: Through which Kafka topic does shipping-service hand requests to carrier-gateway?  
  Status: not_found. Answer: The provided documentation does not state which Kafka topic (or communication mechanism) shipping-service uses to pass requests to carrier-gateway.  
  Cited: []. Required: ['DIAG-01@v1']. Superseded: []
* **D03** (diagram) INCORRECT. Q: When an order is placed, which service is called immediately before payment-service?  
  Status: not_found. Answer: The provided documentation does not state which service is called immediately before payment-service when an order is placed.  
  Cited: []. Required: ['DIAG-02@v1']. Superseded: []
* **D04** (diagram) INCORRECT. Q: In which region does reporting-service run?  
  Status: not_found. Answer: The provided documentation does not specify which region reporting-service runs in.  
  Cited: []. Required: ['DIAG-03@v1']. Superseded: []
* **D05** (diagram) INCORRECT. Q: Which region is the disaster recovery region for Tier 1 services?  
  Status: not_found. Answer: The provided documents do not state which region serves as the disaster recovery region for Tier 1 services.  
  Cited: []. Required: ['DIAG-03@v1']. Superseded: []
* **D06** (diagram) INCORRECT. Q: Into which data warehouse does reporting-service load order events?  
  Status: not_found. Answer: The provided documents do not mention which data warehouse reporting-service loads order events into.  
  Cited: []. Required: ['DIAG-04@v1']. Superseded: []
* **D07** (diagram) INCORRECT. Q: Which service does order-service call first when an order is placed?  
  Status: not_found. Answer: The provided documentation does not specify which service order-service calls first when an order is placed.  
  Cited: []. Required: ['DIAG-02@v1']. Superseded: []
* **D08** (diagram) INCORRECT. Q: Which component sits between carrier-gateway and SwiftShip?  
  Status: answered. Answer: No component sits between carrier-gateway and SwiftShip. carrier-gateway is Northwind's single integration point and talks directly to the SwiftShip API.  
  Cited: ['CT-SWIFT-2024@v1', 'ADR-024@v1']. Required: ['DIAG-01@v1']. Superseded: []

## R1 / gemini-4-argon: 9 incorrect, 4 with a superseded citation
* **X07** (cross_document) INCORRECT. Q: How must payment-service authenticate when it calls inventory-service?  
  Status: answered. Answer: When calling inventory-service, payment-service must authenticate using OAuth2 client credentials issued by identity-service. Specifically, payment-service obtains an access token from identity-service using the client credentials grant and presents it as a bearer token on the request, which invento  
  Cited: ['ADR-011@v1']. Required: ['ADR-011@v1', 'POL-SEC-01@v2']. Superseded: ['POL-SEC-01@v1']
* **C01** (conflicting_versions) correct, but cites a superseded version. Q: Which message broker does Orion use as its event bus today?  
  Status: answered. Answer: Orion uses Apache Kafka as its standard event bus today, superseding the previous decision to use RabbitMQ (which is being phased out in stages).  
  Cited: ['ADR-019@v1', 'ADR-003@v1']. Required: ['ADR-019@v1']. Superseded: ['ADR-003@v1']
* **C03** (conflicting_versions) correct, but cites a superseded version. Q: What rate limit does the SwiftShip contract allow?  
  Status: answered. Answer: Under Amendment 1 of the SwiftShip agreement, the contracted API rate limit is 120 requests per second across Northwind Logistics' entire account (raised from the original limit of 50 requests per second).  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1', 'ADR-024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']
* **C04** (conflicting_versions) correct, but cites a superseded version. Q: Can SwiftShip support be reached at 23:00 Eastern Time?  
  Status: answered. Answer: Yes. Under Amendment 1 of the SwiftShip agreement (CT-SWIFT-2024@A1), vendor support hours were expanded from 06:00–22:00 Eastern Time (in CT-SWIFT-2024@v1) to 24x7, meaning support can be reached at any time of day, on any day.  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']
* **C10** (conflicting_versions) correct, but cites a superseded version. Q: What is the maximum number of retries per carrier request?  
  Status: answered. Answer: The maximum number of retries per carrier request is 3 (using exponential backoff with a 2-second base). This was reduced from the previous limit of 5 in RB-CARRIER-01@v1.  
  Cited: ['RB-CARRIER-01@v2', 'RB-CARRIER-01@v1']. Required: ['RB-CARRIER-01@v2']. Superseded: ['RB-CARRIER-01@v1']
* **D01** (diagram) INCORRECT. Q: Does payment-service call PayNimbus synchronously or asynchronously?  
  Status: not_found. Answer: The provided documentation does not explicitly state whether payment-service calls PayNimbus synchronously or asynchronously (though it notes that initial calls wait up to an 8-second request-response timeout, while failed payments are placed on an asynchronous hourly payment-retry queue).  
  Cited: []. Required: ['DIAG-01@v1']. Superseded: []
* **D02** (diagram) INCORRECT. Q: Through which Kafka topic does shipping-service hand requests to carrier-gateway?  
  Status: not_found. Answer: The provided documents do not mention any Kafka topic or how shipping-service communicates with carrier-gateway.  
  Cited: []. Required: ['DIAG-01@v1']. Superseded: []
* **D03** (diagram) INCORRECT. Q: When an order is placed, which service is called immediately before payment-service?  
  Status: not_found. Answer: The provided documentation does not specify the sequence of service calls when an order is placed or which service is called immediately before payment-service.  
  Cited: []. Required: ['DIAG-02@v1']. Superseded: []
* **D04** (diagram) INCORRECT. Q: In which region does reporting-service run?  
  Status: not_found. Answer: The provided documents do not contain information about the deployment region in which reporting-service runs.  
  Cited: []. Required: ['DIAG-03@v1']. Superseded: []
* **D05** (diagram) INCORRECT. Q: Which region is the disaster recovery region for Tier 1 services?  
  Status: not_found. Answer: The provided documentation states that Tier 1 services must be deployable in the disaster recovery environment, but it does not specify which region serves as the disaster recovery region.  
  Cited: ['POL-DR-02@v1']. Required: ['DIAG-03@v1']. Superseded: []
* **D06** (diagram) INCORRECT. Q: Into which data warehouse does reporting-service load order events?  
  Status: not_found. Answer: The provided documentation does not specify which data warehouse (if any) reporting-service loads order events into.  
  Cited: []. Required: ['DIAG-04@v1']. Superseded: []
* **D07** (diagram) INCORRECT. Q: Which service does order-service call first when an order is placed?  
  Status: not_found. Answer: The provided documents do not specify which service order-service calls first when an order is placed.  
  Cited: []. Required: ['DIAG-02@v1']. Superseded: []
* **D08** (diagram) INCORRECT. Q: Which component sits between carrier-gateway and SwiftShip?  
  Status: answered. Answer: No component sits between carrier-gateway and SwiftShip. Within the Orion platform, carrier-gateway is the single integration point that holds the SwiftShip credentials and talks directly to the SwiftShip carrier API.  
  Cited: ['ADR-024@v1', 'CT-SWIFT-2024@v1']. Required: ['DIAG-01@v1']. Superseded: []

## R2 / gemini-3.8-flash: 4 incorrect, 1 with a superseded citation
* **X07** (cross_document) INCORRECT. Q: How must payment-service authenticate when it calls inventory-service?  
  Status: answered. Answer: When calling inventory-service, payment-service must authenticate using OAuth2 client credentials issued by identity-service. It obtains an access token via the client credentials grant and presents it as a bearer token on the request; there are no exemptions for this call.  
  Cited: ['ADR-011@v1']. Required: ['ADR-011@v1', 'POL-SEC-01@v2']. Superseded: ['POL-SEC-01@v1']
* **C03** (conflicting_versions) correct, but cites a superseded version. Q: What rate limit does the SwiftShip contract allow?  
  Status: answered. Answer: Under Amendment 1 of the SwiftShip carrier services agreement, the contracted API rate limit is 120 requests per second across Northwind Logistics' account (raised from the original limit of 50 requests per second).  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']
* **D01** (diagram) INCORRECT. Q: Does payment-service call PayNimbus synchronously or asynchronously?  
  Status: not_found. Answer: The provided documentation does not state whether payment-service calls PayNimbus synchronously or asynchronously.  
  Cited: []. Required: ['DIAG-01@v1']. Superseded: []
* **D02** (diagram) INCORRECT. Q: Through which Kafka topic does shipping-service hand requests to carrier-gateway?  
  Status: not_found. Answer: The provided documentation does not contain information about the Kafka topic used by shipping-service to communicate with carrier-gateway.  
  Cited: []. Required: ['DIAG-01@v1']. Superseded: []
* **D08** (diagram) INCORRECT. Q: Which component sits between carrier-gateway and SwiftShip?  
  Status: answered. Answer: No component sits between carrier-gateway and SwiftShip. carrier-gateway is Northwind's single integration point within Orion that communicates directly with the SwiftShip API.  
  Cited: ['CT-SWIFT-2024@v1', 'ADR-024@v1']. Required: ['DIAG-01@v1']. Superseded: []

## R2 / gemini-4-argon: 4 incorrect, 2 with a superseded citation
* **X07** (cross_document) INCORRECT. Q: How must payment-service authenticate when it calls inventory-service?  
  Status: answered. Answer: When calling inventory-service, payment-service must authenticate using OAuth2 client credentials issued by identity-service. Specifically, payment-service obtains an access token from identity-service using the client credentials grant and presents it as a bearer token on the request, which invento  
  Cited: ['ADR-011@v1']. Required: ['ADR-011@v1', 'POL-SEC-01@v2']. Superseded: ['POL-SEC-01@v1']
* **C04** (conflicting_versions) correct, but cites a superseded version. Q: Can SwiftShip support be reached at 23:00 Eastern Time?  
  Status: answered. Answer: Yes. Under Amendment 1 of the SwiftShip agreement (CT-SWIFT-2024@A1), vendor support is available 24x7, superseding the original 06:00 to 22:00 Eastern Time support hours in CT-SWIFT-2024@v1.  
  Cited: ['CT-SWIFT-2024@A1', 'CT-SWIFT-2024@v1']. Required: ['CT-SWIFT-2024@A1']. Superseded: ['CT-SWIFT-2024@v1']
* **C10** (conflicting_versions) correct, but cites a superseded version. Q: What is the maximum number of retries per carrier request?  
  Status: answered. Answer: The maximum number of retries per carrier request is 3 (using exponential backoff with a 2-second base). This was reduced from the previous limit of 5 in RB-CARRIER-01@v1.  
  Cited: ['RB-CARRIER-01@v2', 'RB-CARRIER-01@v1']. Required: ['RB-CARRIER-01@v2']. Superseded: ['RB-CARRIER-01@v1']
* **D01** (diagram) INCORRECT. Q: Does payment-service call PayNimbus synchronously or asynchronously?  
  Status: not_found. Answer: The provided documentation does not explicitly state whether payment-service calls PayNimbus synchronously or asynchronously (though it notes that calls wait up to an 8-second timeout from sending a request to receiving a complete response, and that failed attempts are placed on an hourly retry queu  
  Cited: []. Required: ['DIAG-01@v1']. Superseded: []
* **D02** (diagram) INCORRECT. Q: Through which Kafka topic does shipping-service hand requests to carrier-gateway?  
  Status: not_found. Answer: The provided documentation does not mention any Kafka topic or specify how shipping-service communicates with carrier-gateway.  
  Cited: []. Required: ['DIAG-01@v1']. Superseded: []
* **D08** (diagram) INCORRECT. Q: Which component sits between carrier-gateway and SwiftShip?  
  Status: answered. Answer: None. Within the Orion platform, carrier-gateway is the single integration point that communicates directly with the external SwiftShip carrier API (with an internal circuit breaker and outbound rate cap enforced inside carrier-gateway itself).  
  Cited: ['ADR-024@v1', 'CT-SWIFT-2024@v1']. Required: ['DIAG-01@v1']. Superseded: []
