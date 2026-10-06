# IAM setup

## Identity and account placement

Anomalog's backend is the AWS caller. The browser receives log data from FastAPI and never needs AWS credentials. For same-account use, attach the read policy below to the backend's IAM role or development identity. For a deployment in application account A that reads monitoring account B, allow the A role to assume only the B role, trust that A role from B, and attach the read policy to the B role. Configure `AWS_ROLE_ARN` with the B role ARN.

CloudWatch cross-account observability requires the monitoring and source accounts to be linked and log sharing enabled in the chosen Region. `AWS_INCLUDE_LINKED_ACCOUNTS=true` makes the app request linked groups; it does not create the AWS links. Centrally copied logs are separate destination groups owned by the monitoring account. See [AWS cross-account observability setup](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Unified-Cross-Account-Setup.html).

## Runtime permissions

Grant only the capabilities used by the configured mode:

| App capability | IAM action | Scope |
| --- | --- | --- |
| Discover CloudWatch groups, including linked groups | `logs:DescribeLogGroups` | `*` |
| Search CloudWatch or centralized CloudTrail groups | `logs:FilterLogEvents` | Allowed log-group ARNs |
| Start CloudWatch Live Tail | `logs:StartLiveTail` | Allowed log-group ARNs |
| Stop CloudWatch Live Tail | `logs:StopLiveTail` | `*` |
| Regional CloudTrail fallback | `cloudtrail:LookupEvents` | `*` |
| Read OAM links when using cross-account observability | `oam:Get*`, `oam:List*` | `*` |

The first four CloudWatch actions and their resource types are listed in the [CloudWatch Logs authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html). `StopLiveTail` is a permission-only action without a resource type, so it needs its own `Resource: "*"` statement. AWS documents [CloudTrail event-history lookup](https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_LookupEvents.html) and [OAM monitoring permissions](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Unified-Cross-Account-Setup.html) separately.

Example policy for a role with CloudWatch search, Live Tail, and regional CloudTrail fallback enabled. Replace the Region, account ID, and prefix, and add another allowed log-group ARN for each source account whose groups the role may read. Omit the Live Tail, CloudTrail, or OAM statements when that capability is disabled.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "logs:DescribeLogGroups",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:FilterLogEvents", "logs:StartLiveTail"],
      "Resource": "arn:aws:logs:REGION:ACCOUNT_ID:log-group:ALLOWED_PREFIX*"
    },
    {
      "Effect": "Allow",
      "Action": "logs:StopLiveTail",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "cloudtrail:LookupEvents",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["oam:Get*", "oam:List*"],
      "Resource": "*"
    }
  ]
}
```

For account A, the source role needs only this additional permission to assume the monitoring role:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "sts:AssumeRole",
    "Resource": "arn:aws:iam::MONITORING_ACCOUNT_ID:role/AnomalogMonitoringReadRole"
  }]
}
```

The B role must trust the exact A role ARN. Add a `sts:ExternalId` condition if `AWS_ROLE_EXTERNAL_ID` is configured.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::APPLICATION_ACCOUNT_ID:role/AnomalogEc2Role"
    },
    "Action": "sts:AssumeRole"
  }]
}
```

## Acceptance checks

- Confirm the backend can discover an allowed log group and search a narrow time range. A successful `/api/health` response alone does not exercise AWS permissions.
- In linked-account mode, confirm a shared group's ARN and owning account appear in the picker and can be searched. In centralized CloudTrail mode, confirm the intended groups are discoverable or explicitly configured.
- If using regional CloudTrail fallback, confirm a lookup in `AWS_REGION`. If enabling Live Tail, confirm the cost dialog appears before starting and that a stopped session closes. Live Tail verification can incur AWS charges.
- Verify that an unauthorized log group cannot be searched and that the A role cannot assume roles other than the intended B role.
