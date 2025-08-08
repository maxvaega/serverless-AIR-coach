# Authentication Documentation

## Overview

AIR Coach API implements a dual-token authentication system using Auth0 for secure access control. The system handles both client-side JWT tokens for API access and server-side Auth0 management tokens for retrieving user metadata.

## Authentication Flow

### Client to API Authentication

The API uses JWT (JSON Web Tokens) for authenticating client requests:

1. **Token Submission**: Clients must include a valid JWT token in the `Authorization` header using the Bearer scheme:
   ```
   Authorization: Bearer <jwt_token>
   ```

2. **Token Verification**: The `VerifyToken` class in `src/auth.py` handles JWT verification using:
   - **PyJWT library** for token decoding and validation
   - **Auth0 JWKS** (JSON Web Key Set) for signature verification
   - **JWKS URL**: `https://{AUTH0_DOMAIN}/.well-known/jwks.json`

3. **Token Validation Process**:
   - Extract the `kid` (Key ID) from the JWT header
   - Retrieve the corresponding public key from Auth0's JWKS endpoint
   - Verify token signature, audience, issuer, and expiration
   - Return decoded payload with original token for further processing

### JWT Verification Implementation

```python
# src/auth.py - Key components
class VerifyToken:
    def __init__(self):
        self.config = get_settings()
        jwks_url = f'https://{self.config.auth0_domain}/.well-known/jwks.json'
        self.jwks_client = jwt.PyJWKClient(jwks_url)

    async def verify(self, security_scopes, token):
        # Get signing key from JWT
        signing_key = self.jwks_client.get_signing_key_from_jwt(token.credentials).key
        
        # Decode and validate JWT
        payload = jwt.decode(
            token.credentials,
            signing_key,
            algorithms=self.config.auth0_algorithms,
            audience=self.config.auth0_api_audience,
            issuer=self.config.auth0_issuer,
        )
        
        return {**payload, 'token': token.credentials}
```

## Auth0 Token Management

### Management Token for API Calls

The application uses Auth0's Management API to retrieve user metadata, requiring a separate management token:

1. **Token Acquisition**: Uses client credentials flow to obtain management token
2. **Caching Strategy**: Tokens are cached for 24 hours to minimize API calls
3. **Automatic Renewal**: New tokens are requested when cache expires

### Implementation Details

```python
# src/auth0.py - Management token flow
def get_auth0_token():
    # Check cache first
    token = get_cached_auth0_token()
    if token:
        return token
    
    # Request new token using client credentials
    payload = {
        'grant_type': 'client_credentials',
        'client_id': 'MRSjewKmL15bVGQoBWJlEFUTK57lykvj',
        'client_secret': AUTH0_SECRET,
        'audience': f"https://{AUTH0_DOMAIN}/api/v2/"
    }
    
    # Cache token for 24 hours
    set_cached_auth0_token(access_token)
```

## Token Caching Strategy

The application implements a multi-level caching system using `cachetools.TTLCache`:

### Cache Types

1. **Auth0 Management Token Cache**:
   - **TTL**: 24 hours (86400 seconds)
   - **Size**: 1 entry (single token)
   - **Purpose**: Minimize Auth0 API calls for management operations

2. **User Metadata Cache**:
   - **TTL**: 10 minutes (600 seconds)
   - **Size**: 1000 entries
   - **Purpose**: Cache formatted user metadata to reduce Auth0 API calls

### Cache Implementation

```python
# src/cache.py
from cachetools import TTLCache

# Auth0 management token cache (24h TTL)
auth0_token_cache = TTLCache(maxsize=1, ttl=86400)

# User metadata cache (10min TTL)
user_metadata_cache = TTLCache(maxsize=1000, ttl=600)
```

## Supported User ID Formats

The system supports two user ID formats from Auth0 identity providers:

### Auth0 Database Users
- **Format**: `auth0|[24 hexadecimal characters]`
- **Example**: `auth0|507f1f77bcf86cd799439011`
- **Regex**: `^auth0\|[0-9a-fA-F]{24}$`

### Google OAuth2 Users
- **Format**: `google-oauth2|[15-25 digits]`
- **Example**: `google-oauth2|104612087445133776110`
- **Regex**: `^google-oauth2\|[0-9]{15,25}$`

### Validation Implementation

```python
# src/utils.py
def validate_user_id(user_id):
    auth0_pattern = r'^auth0\|[0-9a-fA-F]{24}$'
    google_pattern = r'^google-oauth2\|[0-9]{15,25}$'
    
    return re.match(auth0_pattern, user_id) or re.match(google_pattern, user_id)
```

## Error Handling

### Authentication Errors

The system provides specific error responses for different authentication failures:

#### 401 Unauthorized
- **Cause**: Missing Authorization header
- **Response**: `{"detail": "Requires authentication"}`
- **Class**: `UnauthenticatedException`

#### 403 Forbidden
- **Causes**:
  - Invalid JWT signature
  - Expired token
  - Invalid audience or issuer
  - Malformed token
- **Response**: `{"detail": "<specific_error_message>"}`
- **Class**: `UnauthorizedException`

### Error Classes

```python
# src/auth.py
class UnauthenticatedException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Requires authentication"
        )

class UnauthorizedException(HTTPException):
    def __init__(self, detail: str, **kwargs):
        super().__init__(status.HTTP_403_FORBIDDEN, detail=detail)
```

## Required Environment Variables

### Auth0 Configuration

The following environment variables must be configured for authentication to work:

```bash
# Auth0 Domain (required)
AUTH0_DOMAIN=your-auth0-domain.auth0.com

# Auth0 Management API Secret (required)
AUTH0_SECRET=your-auth0-client-secret

# Auth0 API Audience (required)
AUTH0_API_AUDIENCE=your-auth0-api-audience

# Auth0 Issuer (required)
AUTH0_ISSUER=https://your-auth0-domain.auth0.com/

# Auth0 Algorithms (optional, defaults to RS256)
AUTH0_ALGORITHMS=RS256
```

### Environment Variable Descriptions

- **AUTH0_DOMAIN**: Your Auth0 tenant domain
- **AUTH0_SECRET**: Client secret for Auth0 Management API access
- **AUTH0_API_AUDIENCE**: Identifier for your Auth0 API
- **AUTH0_ISSUER**: Token issuer URL (typically your Auth0 domain with https://)
- **AUTH0_ALGORITHMS**: Comma-separated list of allowed JWT algorithms

## User Metadata Integration

### Metadata Retrieval Process

1. **Token Validation**: Client JWT is validated first
2. **User ID Extraction**: User ID is extracted from the request
3. **Cache Check**: System checks if user metadata is cached
4. **Auth0 API Call**: If not cached, retrieves metadata from Auth0 Management API
5. **Formatting**: Metadata is formatted for LLM context
6. **Caching**: Formatted metadata is cached for 10 minutes

### Metadata Fields

The system processes the following user metadata fields:

- **Personal Information**: name, surname, date_of_birth, sex
- **Parachuting Experience**: jumps (experience level), qualifications
- **Preferences**: preferred_dropzone

### Metadata Formatting

User metadata is formatted into a human-readable string for LLM context:

```python
# Example formatted output
"""
I dati che l'utente ti ha fornito su di sè sono:
Data di Nascita: 1990-01-01
Numero di salti: 51 - 150
Dropzone preferita: Skydive Milano
qualifica: Paracadutista licenziato
Nome: Mario
Cognome: Rossi
Sesso: Maschio

Oggi è il 2024-01-15
"""
```

## Security Considerations

### Token Security
- JWT tokens are validated using Auth0's public keys
- Tokens are never stored permanently on the server
- Management tokens are cached securely in memory only

### Best Practices
- Always use HTTPS in production
- Regularly rotate Auth0 client secrets
- Monitor authentication logs for suspicious activity
- Implement proper CORS policies

### Rate Limiting
- Auth0 Management API calls are minimized through caching
- User metadata cache reduces API load
- Consider implementing additional rate limiting for high-traffic scenarios

## Troubleshooting

### Common Issues

1. **403 Forbidden Errors**:
   - Check JWT token validity and expiration
   - Verify Auth0 configuration (domain, audience, issuer)
   - Ensure JWKS endpoint is accessible

2. **User Metadata Not Loading**:
   - Verify AUTH0_SECRET is correct
   - Check Auth0 Management API permissions
   - Validate user ID format

3. **Cache Issues**:
   - Monitor cache TTL settings
   - Check memory usage for large user bases
   - Consider cache size limits

### Debug Logging

Enable debug logging to troubleshoot authentication issues:

```python
# Check logs for authentication events
logger.info(f"Request received: token={token} userid={request.userid}")
logger.info("Auth0: Token found in cache")
logger.error(f"Auth0: Error during token retrieval: {e}")
```
