# Database Connection Pool Exhaustion Runbook

## Symptoms

- Application services reporting "connection pool exhausted" errors
- Database connection timeouts in application logs
- HTTP 503 Service Unavailable errors from affected services
- Increased API latency and timeout errors
- Health check failures for database-dependent services
- Monitoring dashboards showing connection pool at 100% utilization

## Diagnostic Checks

1. **Check Connection Pool Utilization**
   - Review database connection pool metrics
   - Identify current active connections vs. pool limit
   - Look for sustained high utilization (>90%)

2. **Identify Long-Running Queries**
   - Query the database for active queries and their duration
   - Check for queries running longer than expected (>60 seconds)
   - Identify the source application or worker for long-running queries

3. **Review Application Logs**
   - Search for "connection timeout" or "pool exhausted" errors
   - Identify which services are experiencing connection failures
   - Check timestamps to establish incident timeline

4. **Check for Connection Leaks**
   - Review connection acquisition and release patterns
   - Look for services that acquire but don't properly release connections
   - Check for recent deployments that might have introduced leaks

5. **Analyze Query Patterns**
   - Look for sudden increases in query volume
   - Identify expensive queries (large table scans, complex joins)
   - Check for batch jobs or reporting queries running during peak hours

## Remediation Steps

### Immediate Actions

1. **Identify and Address Active Long-Running Queries**
   - Locate queries running longer than normal operational thresholds
   - Contact the team responsible for the source application
   - **WARNING: Do not automatically terminate queries without approval**
   - Coordinate with application owners before taking action

2. **Scale Connection Pool (If Possible)**
   - Temporarily increase connection pool size if infrastructure allows
   - Monitor database server resource utilization (CPU, memory, connections)
   - Ensure database server can handle additional connections

3. **Restart Affected Services (Last Resort)**
   - If connection leaks are suspected and pool cannot be expanded
   - Perform rolling restart to minimize impact
   - Document the decision and coordinate with on-call team

### Short-Term Fixes

1. **Reschedule Non-Critical Operations**
   - Move batch jobs and reporting queries to off-peak hours
   - Implement query timeouts for background jobs
   - Add connection pool monitoring for background workers

2. **Optimize Query Performance**
   - Review slow query logs
   - Add appropriate indexes for frequently-run queries
   - Consider read replicas for reporting workloads

### Long-Term Prevention

1. **Implement Connection Pool Monitoring**
   - Set up alerts for high connection pool utilization (>80%)
   - Track connection acquisition times
   - Monitor per-service connection usage

2. **Review Connection Pool Configuration**
   - Tune pool sizes based on actual usage patterns
   - Implement connection timeouts and idle connection limits
   - Configure separate pools for batch jobs vs. real-time operations

3. **Establish Query Governance**
   - Implement query timeout limits
   - Require performance testing for new reporting queries
   - Use read replicas for analytical workloads

## Escalation Conditions

Escalate to database team if:
- Database server resources (CPU, memory) are maxed out
- Connection pool cannot be expanded due to server limits
- Issue persists after addressing application-side causes
- Data corruption or integrity concerns arise

Escalate to management if:
- Customer-facing impact exceeds 30 minutes
- Revenue-generating services are affected
- Issue requires emergency change control

## Safety Warnings

⚠️ **Do not terminate database queries without coordination**
- Long-running queries may be critical batch operations
- Terminating queries can cause data inconsistency
- Always contact the application owner first

⚠️ **Do not restart database server without approval**
- This affects all connected services
- Requires change control approval
- Should only be done as absolute last resort

⚠️ **Do not modify connection pool limits without testing**
- Database server has finite connection capacity
- Excessive connections can degrade database performance
- Test changes in staging environment first
