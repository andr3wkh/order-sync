# AWS Lambda Deployment Guide

## Prerequisites

1. **AWS Account** with Lambda access
2. **GitHub Repository** for your code
3. **PostgreSQL Database** (accessible from Lambda - e.g., AWS RDS)

## Step 1: Set Up AWS Lambda Function

### Create Lambda Function via AWS Console:

1. Go to AWS Lambda Console
2. Click "Create function"
3. Choose "Author from scratch"
4. Configure:
   - **Function name**: `order-sync-function` (or your choice)
   - **Runtime**: Python 3.11
   - **Architecture**: x86_64
   - **Execution role**: Create a new role with basic Lambda permissions

### Configure Lambda Settings:

1. **Memory**: 512 MB (adjust based on order volume)
2. **Timeout**: 5 minutes (adjust based on sync duration)
3. **Handler**: `lambda_handler.lambda_handler`

### Set Up VPC (if using RDS):

If your database is in a VPC (like RDS), configure:
- VPC
- Subnets (private subnets recommended)
- Security Groups (allow outbound HTTPS and PostgreSQL)

### Add Environment Variables (Optional):

You can set these in Lambda directly or via GitHub Actions:
- `DATABASE_URL`: Your PostgreSQL connection string
- `POLL_INTERVAL`: Not used in Lambda (kept for local compatibility)

## Step 2: Create EventBridge Schedule (Optional)

To run your Lambda on a schedule:

1. Go to Amazon EventBridge
2. Create a new rule
3. Choose "Schedule"
4. Set schedule (e.g., `rate(5 minutes)` or cron expression)
5. Select target: Your Lambda function

Example cron: `cron(*/5 * * * ? *)` - runs every 5 minutes

## Step 3: Configure GitHub Secrets

In your GitHub repository, add these secrets (Settings → Secrets and variables → Actions):

### Required Secrets:
- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
- `AWS_REGION`: Your Lambda region (e.g., `us-east-1`)
- `LAMBDA_FUNCTION_NAME`: Your Lambda function name (e.g., `order-sync-function`)
- `DATABASE_URL`: Your PostgreSQL connection string

### Create AWS IAM User for GitHub Actions:

1. Go to IAM → Users → Add user
2. User name: `github-actions-lambda-deploy`
3. Attach policies:
   - `AWSLambda_FullAccess` (or create custom policy with minimum permissions)
4. Create access key → Store in GitHub Secrets

### Minimum IAM Policy for GitHub Actions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:PublishVersion"
      ],
      "Resource": "arn:aws:lambda:REGION:ACCOUNT_ID:function:order-sync-function"
    }
  ]
}
```

## Step 4: Deploy to GitHub

1. **Initialize Git Repository:**
```bash
git init
git add .
git commit -m "Initial commit"
```

2. **Create GitHub Repository:**
   - Go to GitHub and create a new repository
   - Don't initialize with README (you already have one)

3. **Push to GitHub:**
```bash
git remote add origin https://github.com/YOUR_USERNAME/order-sync.git
git branch -M main
git push -u origin main
```

## Step 5: Deploy via GitHub Actions

Once you push to the `main` branch, GitHub Actions will automatically:
1. Check out your code
2. Install Python dependencies
3. Create a deployment package
4. Deploy to AWS Lambda
5. Update environment variables
6. Publish a new version

You can also manually trigger deployment:
- Go to Actions tab in GitHub
- Select "Deploy to AWS Lambda"
- Click "Run workflow"

## Testing Your Lambda

### Test via AWS Console:
1. Go to Lambda function
2. Click "Test"
3. Create test event (can be empty JSON `{}`)
4. Click "Test"
5. Check CloudWatch Logs for output

### Test via AWS CLI:
```bash
aws lambda invoke \
  --function-name order-sync-function \
  --payload '{}' \
  response.json

cat response.json
```

### Monitor CloudWatch Logs:
```bash
aws logs tail /aws/lambda/order-sync-function --follow
```

## Deployment Workflow

```
┌─────────────┐
│  Git Push   │
│  to main    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ GitHub Actions  │
│  - Build        │
│  - Package      │
│  - Deploy       │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  AWS Lambda     │
│  - Updated Code │
│  - New Version  │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  EventBridge    │
│  (Scheduled)    │
│  Triggers       │
└─────────────────┘
```

## Troubleshooting

### Lambda times out:
- Increase timeout in Lambda settings
- Check database connectivity
- Review CloudWatch Logs

### Dependencies missing:
- Ensure `requirements.txt` is complete
- Check deployment package includes all files

### Database connection fails:
- Verify `DATABASE_URL` is correct
- Check VPC/Security Group settings
- Ensure Lambda has internet access (NAT Gateway for private subnet)

### GitHub Actions fails:
- Verify all secrets are set correctly
- Check IAM permissions
- Review Actions logs

## Cost Optimization

- **Lambda**: Free tier includes 1M requests/month
- **EventBridge**: Minimal cost for schedules
- **RDS**: Use appropriate instance size
- **CloudWatch Logs**: Set retention period (7-30 days)

## Security Best Practices

1. ✅ Store credentials in GitHub Secrets (never commit)
2. ✅ Use IAM roles with least privilege
3. ✅ Keep Lambda in private subnet (if using VPC)
4. ✅ Encrypt environment variables (Lambda default)
5. ✅ Regularly rotate AWS access keys
6. ✅ Enable CloudWatch Logs encryption
7. ✅ Use SSL for database connections

## Next Steps

- Set up CloudWatch alarms for Lambda errors
- Configure Dead Letter Queue (DLQ) for failed invocations
- Implement Lambda versioning and aliases
- Add monitoring dashboard
- Set up SNS notifications for errors
