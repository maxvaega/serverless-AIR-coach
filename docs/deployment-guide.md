# Deployment and Configuration Guide

## Overview

This guide provides comprehensive instructions for deploying and configuring the AIR Coach API. The application is designed for serverless deployment on Vercel with integrations to Auth0, MongoDB, AWS S3, and Google AI services.

## Environment Variables Reference

### Complete Environment Variables List

The application requires the following environment variables for proper operation:

```bash
# Google AI Configuration (Required)
GOOGLE_API_KEY=your-google-ai-api-key

# Langsmith Tracing (Optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your-langchain-api-key
LANGCHAIN_PROJECT=air-coach-project

# MongoDB Configuration (Required)
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
DATABASE_NAME=conversations
COLLECTION_NAME=chat_history

# AWS S3 Configuration (Required)
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
BUCKET_NAME=your-s3-bucket-name

# Auth0 Configuration (Required)
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_SECRET=your-auth0-client-secret
AUTH0_API_AUDIENCE=your-auth0-api-identifier
AUTH0_ISSUER=https://your-tenant.auth0.com/
AUTH0_ALGORITHMS=RS256

# Application Configuration (Optional)
ENVIRONMENT=production
FORCED_MODEL=models/gemini-2.5-flash
```

### Environment Variable Descriptions

#### Google AI Configuration

**GOOGLE_API_KEY** (Required)
- **Description**: API key for Google AI Gemini model access
- **Format**: String (typically 39 characters)
- **Example**: `AIzaSyDaGmWKa4JsXZ5iQuzbl3lOh2A1B2C3D4E`
- **Obtain from**: [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Permissions**: Generative AI API access

#### Langsmith Configuration (Optional)

**LANGCHAIN_TRACING_V2** (Optional)
- **Description**: Enable Langchain tracing for monitoring
- **Values**: `true` or `false`
- **Default**: `false` (disabled)

**LANGCHAIN_ENDPOINT** (Optional)
- **Description**: Langsmith API endpoint
- **Default**: `https://api.smith.langchain.com`

**LANGCHAIN_API_KEY** (Optional)
- **Description**: API key for Langsmith service
- **Obtain from**: [Langsmith Console](https://smith.langchain.com/)

**LANGCHAIN_PROJECT** (Optional)
- **Description**: Project name for organizing traces
- **Format**: String (project identifier)

#### MongoDB Configuration

**MONGODB_URI** (Required)
- **Description**: MongoDB connection string
- **Format**: `mongodb+srv://username:password@cluster.mongodb.net/database`
- **Example**: `mongodb+srv://aircoach:password123@cluster0.abc123.mongodb.net/`
- **Security**: Use MongoDB Atlas for managed hosting

**DATABASE_NAME** (Required)
- **Description**: MongoDB database name
- **Default**: `conversations`
- **Format**: String (valid MongoDB database name)

**COLLECTION_NAME** (Required)
- **Description**: MongoDB collection for chat history
- **Default**: `chat_history`
- **Format**: String (valid MongoDB collection name)

#### AWS S3 Configuration

**AWS_ACCESS_KEY_ID** (Required)
- **Description**: AWS access key for S3 operations
- **Format**: 20-character alphanumeric string
- **Example**: `AKIAIOSFODNN7EXAMPLE`
- **Permissions**: S3 read/write access to specified bucket

**AWS_SECRET_ACCESS_KEY** (Required)
- **Description**: AWS secret key corresponding to access key
- **Format**: 40-character base64-encoded string
- **Security**: Keep secret, rotate regularly

**BUCKET_NAME** (Required)
- **Description**: S3 bucket name for document storage
- **Format**: Valid S3 bucket name (lowercase, no spaces)
- **Example**: `air-coach-documents`
- **Structure**: Must contain `docs/` folder for Markdown files

#### Auth0 Configuration

**AUTH0_DOMAIN** (Required)
- **Description**: Auth0 tenant domain
- **Format**: `tenant-name.auth0.com` or custom domain
- **Example**: `air-coach.auth0.com`
- **Obtain from**: Auth0 Dashboard → Applications → Settings

**AUTH0_SECRET** (Required)
- **Description**: Auth0 application client secret
- **Format**: Base64-encoded string
- **Security**: Keep secret, available in Auth0 application settings
- **Purpose**: Used for Auth0 Management API access

**AUTH0_API_AUDIENCE** (Required)
- **Description**: Auth0 API identifier
- **Format**: URI or identifier string
- **Example**: `https://api.air-coach.com`
- **Configure in**: Auth0 Dashboard → APIs

**AUTH0_ISSUER** (Required)
- **Description**: JWT token issuer URL
- **Format**: `https://your-domain.auth0.com/`
- **Note**: Must end with trailing slash

**AUTH0_ALGORITHMS** (Optional)
- **Description**: Allowed JWT signing algorithms
- **Default**: `RS256`
- **Format**: Comma-separated list
- **Example**: `RS256,HS256`

#### Application Configuration

**ENVIRONMENT** (Optional)
- **Description**: Application environment mode
- **Values**: `production` or `development`
- **Default**: `development`
- **Impact**: Controls API docs availability and logging level

**FORCED_MODEL** (Optional)
- **Description**: Override default Gemini model
- **Default**: `models/gemini-2.5-flash`
- **Options**: Any valid Gemini model identifier
- **Example**: `models/gemini-2.5-flash-lite`

## Secrets Management Best Practices

### Environment-Specific Configuration

#### Development Environment
```bash
# .env.local (for local development)
GOOGLE_API_KEY=dev-api-key
MONGODB_URI=mongodb://localhost:27017/aircoach-dev
AUTH0_DOMAIN=dev-tenant.auth0.com
ENVIRONMENT=development
```

#### Production Environment
- Use Vercel environment variables (encrypted at rest)
- Never commit secrets to version control
- Use different Auth0 tenants for dev/staging/production
- Implement secret rotation policies

### Security Recommendations

1. **Secret Rotation**:
   - Rotate Auth0 client secrets every 90 days
   - Rotate AWS keys every 180 days
   - Monitor Google AI API key usage

2. **Access Control**:
   - Use IAM roles with minimal permissions
   - Implement IP restrictions where possible
   - Enable audit logging for all services

3. **Environment Isolation**:
   - Separate credentials for each environment
   - Use different MongoDB databases/clusters
   - Isolate S3 buckets by environment

## Vercel Deployment Process

### Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Repository**: Code must be in a Git repository
3. **Environment Variables**: All required variables configured

### Deployment Steps

#### 1. Initial Setup

```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Initialize project
vercel
```

#### 2. Configure Build Settings

The `vercel.json` configuration is already optimized:

```json
{
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "app.py" },
    { "src": "/(.*)", "dest": "app.py" }
  ],
  "env": {
    "PYTHONPATH": "."
  }
}
```

#### 3. Environment Variables Configuration

In Vercel Dashboard:
1. Go to Project Settings → Environment Variables
2. Add all required environment variables
3. Set appropriate environments (Production, Preview, Development)

#### 4. Deployment Commands

```bash
# Deploy to preview
vercel

# Deploy to production
vercel --prod

# Check deployment status
vercel ls
```

### Vercel Configuration Options

#### Build Configuration
- **Runtime**: Python 3.9+
- **Memory**: 1024MB (default)
- **Timeout**: 10 seconds (default)
- **Regions**: Global edge deployment

#### Custom Domains
```bash
# Add custom domain
vercel domains add api.air-coach.com

# Configure DNS
# Add CNAME record: api.air-coach.com → cname.vercel-dns.com
```

## MongoDB Setup and Connection Requirements

### MongoDB Atlas Setup

#### 1. Create Cluster

1. Sign up at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Create a new cluster (M0 free tier available)
3. Choose cloud provider and region
4. Configure cluster name

#### 2. Database Configuration

```javascript
// Database structure
{
  "database": "conversations",
  "collections": [
    {
      "name": "chat_history",
      "indexes": [
        { "timestamp": -1 },  // Primary index for recent messages
        { "userId": 1, "timestamp": -1 }  // Compound index for user queries
      ]
    }
  ]
}
```

#### 3. Security Configuration

```bash
# Create database user
Username: aircoach-api
Password: [generate strong password]
Roles: readWrite on conversations database

# Network access
IP Whitelist: 0.0.0.0/0 (for Vercel serverless)
# Note: Vercel uses dynamic IPs, so broad access is required
```

#### 4. Connection String Format

```bash
MONGODB_URI=mongodb+srv://username:password@cluster0.abc123.mongodb.net/conversations?retryWrites=true&w=majority
```

### Index Optimization

```javascript
// Recommended indexes for optimal performance
db.chat_history.createIndex({ "timestamp": -1 }, { background: true })
db.chat_history.createIndex({ "userId": 1, "timestamp": -1 }, { background: true })

// Query performance verification
db.chat_history.find({"userId": "auth0|123"}).sort({"timestamp": -1}).limit(10).explain()
```

### Connection Monitoring

- Monitor connection pool usage
- Set up alerts for connection failures
- Configure read/write concern for consistency

## AWS S3 Bucket Configuration

### S3 Bucket Setup

#### 1. Create Bucket

```bash
# Using AWS CLI
aws s3 mb s3://air-coach-documents --region us-east-1

# Or use AWS Console
# 1. Go to S3 Console
# 2. Create bucket with unique name
# 3. Choose appropriate region
```

#### 2. Bucket Structure

```
air-coach-documents/
├── docs/
│   ├── safety-procedures.md
│   ├── equipment-guide.md
│   ├── training-manual.md
│   └── regulations.md
└── prompt/
    └── system_prompt.md (auto-generated)
```

#### 3. IAM Policy Configuration

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::air-coach-documents",
        "arn:aws:s3:::air-coach-documents/*"
      ]
    }
  ]
}
```

#### 4. CORS Configuration

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST"],
    "AllowedOrigins": ["*"],
    "ExposeHeaders": []
  }
]
```

### Document Management

#### Document Format Requirements
- **File Type**: Markdown (.md)
- **Encoding**: UTF-8
- **Location**: Must be in `docs/` prefix
- **Naming**: Descriptive filenames (kebab-case recommended)

#### Content Guidelines
```markdown
# Document Title

## Section 1
Content for the AI system prompt...

## Section 2
Additional context and procedures...
```

## Auth0 Application Setup

### Auth0 Configuration

#### 1. Create Auth0 Account
1. Sign up at [auth0.com](https://auth0.com)
2. Create a new tenant
3. Choose region closest to your users

#### 2. Application Setup

```bash
# Application Type: Single Page Application (SPA)
# or Regular Web Application based on your frontend

Application Settings:
- Name: AIR Coach API
- Type: Single Page Application
- Allowed Callback URLs: https://your-frontend-domain.com/callback
- Allowed Logout URLs: https://your-frontend-domain.com
- Allowed Web Origins: https://your-frontend-domain.com
```

#### 3. API Configuration

```bash
# Create API in Auth0 Dashboard
API Settings:
- Name: AIR Coach API
- Identifier: https://api.air-coach.com (use as AUTH0_API_AUDIENCE)
- Signing Algorithm: RS256
```

#### 4. Machine-to-Machine Application

```bash
# For Auth0 Management API access
Application Type: Machine to Machine
Authorized APIs: Auth0 Management API
Scopes: read:users, read:user_idp_tokens
```

### User Management

#### User Metadata Schema

```json
{
  "user_metadata": {
    "name": "string",
    "surname": "string", 
    "date_of_birth": "YYYY-MM-DD",
    "sex": "MASCHIO|FEMMINA|SCONOSCIUTO",
    "jumps": "0_10|11_50|51_150|151_300|301_1000|1000+",
    "qualifications": "NO_PARACADUTISMO|ALLIEVO|LICENZIATO|DL|IP",
    "preferred_dropzone": "string"
  }
}
```

#### Identity Providers

```bash
# Supported providers
- Auth0 Database: auth0|[24 hex chars]
- Google OAuth2: google-oauth2|[15-25 digits]

# Configuration in Auth0 Dashboard → Authentication → Social
```

## Google AI API Setup

### API Key Generation

#### 1. Google AI Studio Setup
1. Visit [Google AI Studio](https://makersuite.google.com/)
2. Sign in with Google account
3. Create new project or select existing
4. Generate API key

#### 2. API Key Configuration

```bash
# API Key format
GOOGLE_API_KEY=AIzaSyDaGmWKa4JsXZ5iQuzbl3lOh2A1B2C3D4E

# Restrictions (recommended)
- HTTP referrers: your-domain.com/*
- IP addresses: Vercel IP ranges (if static)
- APIs: Generative Language API only
```

#### 3. Model Configuration

```python
# Available models (as of 2024)
FORCED_MODEL options:
- "models/gemini-2.5-flash"      # Default, balanced performance
- "models/gemini-2.5-flash-lite" # Faster, lighter responses  
- "models/gemini-pro"            # Higher quality, slower
```

### Usage Monitoring

#### Quota Management
- Monitor API usage in Google Cloud Console
- Set up billing alerts
- Implement rate limiting if needed

#### Performance Optimization
```python
# Model parameters for optimal performance
{
    "temperature": 0.1,        # Consistent responses
    "max_tokens": None,        # No artificial limits
    "timeout": None,           # Let Langchain handle
    "max_retries": 2          # Automatic retry on failure
}
```

## Monitoring and Logging Configuration

### Application Logging

#### Logging Configuration

```python
# src/logging_config.py
import logging
import sys

# Production logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Development logging (more verbose)
if not is_production:
    logging.getLogger().setLevel(logging.DEBUG)
```

#### Log Levels and Usage

```python
# Critical application events
logger.error("Auth0: Error during token retrieval")
logger.warning("User metadata: Unrecognized qualification")
logger.info("Request received: token=xxx message=xxx userid=xxx")
logger.debug("Cache hit for user metadata")
```

### Vercel Monitoring

#### Built-in Monitoring
- **Function Logs**: Available in Vercel Dashboard
- **Performance Metrics**: Response times, error rates
- **Usage Analytics**: Request volume, bandwidth

#### Custom Monitoring Setup

```bash
# Environment variables for monitoring
VERCEL_URL=your-deployment-url.vercel.app
VERCEL_ENV=production
VERCEL_REGION=iad1
```

### External Monitoring Integration

#### Langsmith Tracing

```bash
# Enable comprehensive LLM monitoring
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your-langchain-key
LANGCHAIN_PROJECT=air-coach-production

# Monitored metrics:
- LLM response times
- Token usage and costs
- Error rates and types
- User interaction patterns
```

#### Health Check Endpoints

```python
# Recommended health check implementation
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0",
        "services": {
            "mongodb": await check_mongodb_connection(),
            "s3": await check_s3_access(),
            "auth0": await check_auth0_connectivity()
        }
    }
```

### Alerting Configuration

#### Critical Alerts
- **High Error Rate**: >5% 4xx/5xx responses
- **Slow Response Time**: >10s average response time
- **Service Unavailability**: MongoDB/S3/Auth0 connection failures
- **Cache Performance**: <80% cache hit rate

#### Monitoring Tools Integration
```bash
# Recommended monitoring services
- Vercel Analytics (built-in)
- Langsmith (LLM-specific)
- MongoDB Atlas Monitoring
- AWS CloudWatch (S3 metrics)
- Auth0 Logs and Analytics
```

## Deployment Checklist

### Pre-Deployment Verification

- [ ] All environment variables configured
- [ ] MongoDB cluster accessible and indexed
- [ ] S3 bucket created with proper permissions
- [ ] Auth0 application and API configured
- [ ] Google AI API key generated and restricted
- [ ] Domain DNS configured (if using custom domain)

### Post-Deployment Verification

- [ ] Health check endpoint responds successfully
- [ ] Authentication flow works end-to-end
- [ ] Document loading from S3 functions
- [ ] Chat history persistence to MongoDB
- [ ] Streaming responses work correctly
- [ ] Error handling returns appropriate status codes
- [ ] Monitoring and logging operational

### Production Readiness

- [ ] HTTPS enforced for all communications
- [ ] CORS configured for production domains only
- [ ] Rate limiting implemented (if required)
- [ ] Backup and disaster recovery plan
- [ ] Security audit completed
- [ ] Performance testing passed
- [ ] Documentation updated and accessible

## Troubleshooting Common Issues

### Deployment Issues

**Build Failures**
```bash
# Check Python version compatibility
python --version  # Should be 3.9+

# Verify requirements.txt
pip install -r requirements.txt

# Check vercel.json syntax
vercel dev  # Test locally first
```

**Environment Variable Issues**
```bash
# Verify all required variables are set
vercel env ls

# Test environment variable access
vercel dev
# Check logs for missing variable errors
```

### Runtime Issues

**Authentication Failures**
- Verify Auth0 domain and issuer URLs
- Check JWT token format and expiration
- Validate JWKS endpoint accessibility

**Database Connection Issues**
- Verify MongoDB URI format and credentials
- Check network access whitelist (0.0.0.0/0 for Vercel)
- Test connection from local environment

**S3 Access Issues**
- Verify AWS credentials and permissions
- Check bucket name and region configuration
- Test S3 access with AWS CLI

### Performance Issues

**Slow Response Times**
- Monitor cache hit rates
- Check external service latencies
- Optimize MongoDB queries with proper indexes

**Memory Issues**
- Monitor Vercel function memory usage
- Optimize cache sizes if needed
- Consider upgrading Vercel plan for more memory
