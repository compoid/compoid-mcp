# Security Policy

## 🔒 Security Overview

The Compoid MCP Server takes security seriously. This document outlines our security practices, vulnerability disclosure policy, and best practices for users.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅        |
| < 1.0   | ❌        |

## 🔐 Security Features

### Authentication & Authorization
- **API Key Management**: All API keys are handled securely and never logged
- **Header-Based Auth**: Supports both Bearer tokens and custom headers
- **User-Specific Keys**: MCP proxy supports per-user API key injection via HTTP headers
- **No Key Storage**: Keys are passed through, not stored by the server

### Data Protection
- **HTTPS Only**: All remote server communications use HTTPS
- **No Persistent Storage**: The MCP server doesn't store user data
- **Rate Limiting**: Built-in rate limiting prevents abuse
- **Input Validation**: All inputs are validated before API calls

### Network Security
- **TLS 1.2+**: All connections use modern TLS
- **Certificate Validation**: SSL/TLS certificates are validated
- **No Plain Text**: Sensitive data never transmitted in plain text

## 🛡️ Best Practices

### For Users

1. **Protect Your API Keys**
   ```bash
   # ✅ Good: Use environment variables
   export COMPOID_REPO_API_KEY="your-key-here"
   
   # ❌ Bad: Hardcode in scripts
   curl -H "Authorization: Bearer your-key-here"
   ```

2. **Use Environment Variables**
   ```json
   {
     "mcpServers": {
       "Compoid": {
         "env": {
           "COMPOID_REPO_API_KEY": "${COMPOID_REPO_API_KEY}"
         }
       }
     }
   }
   ```

3. **Limit Permissions**
   - Only request necessary API scopes
   - Use separate keys for development/production
   - Rotate keys periodically

4. **Monitor Usage**
   - Check API usage logs regularly
   - Set up alerts for unusual activity
   - Review rate limit warnings

### For Developers

1. **Never Log Sensitive Data**
   ```python
   # ❌ Bad
   logger.debug(f"API Key: {config.repo_api_key}")
   
   # ✅ Good
   logger.debug(f"API Key configured: {bool(config.repo_api_key)}")
   ```

2. **Validate All Inputs**
   ```python
   # ✅ Validate before use
   if not work_id or not isinstance(work_id, str):
       raise ValueError("Invalid work_id")
   ```

3. **Use Prepared Statements** (if using databases)
4. **Implement Rate Limiting**
5. **Sanitize User Input**

## 🚨 Reporting a Vulnerability

We take all security reports seriously. Thank you for helping keep Compoid safe.

### How to Report

1. **DO NOT** create a public GitHub issue for security vulnerabilities
2. **DO** send a private report to: `security@compoid.com`
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Initial Response**: Within 48 hours
- **Acknowledgment**: We'll confirm receipt of your report
- **Investigation**: Typically completed within 7 days
- **Resolution**: Timeline depends on complexity
- **Credit**: We'll credit you in release notes (if desired)

### Security Updates

- Critical vulnerabilities are patched within 7 days
- High severity: 14 days
- Medium severity: 30 days
- Low severity: Next release

## 📋 Known Security Considerations

### API Key Exposure
- **Risk**: API keys in client configurations
- **Mitigation**: Use environment variables, never commit to git
- **Status**: ⚠️ User responsibility

### Rate Limiting Bypass
- **Risk**: Multiple instances could exceed rate limits
- **Mitigation**: Server-side rate limiting per API key
- **Status**: ✅ Protected

### File Upload Validation
- **Risk**: Malicious files could be uploaded
- **Mitigation**: MIME type checking, file size limits
- **Status**: ✅ Protected

### XXE/SSRF
- **Risk**: XML external entity or server-side request forgery
- **Mitigation**: Input validation, URL allowlists
- **Status**: ✅ Protected

## 🔍 Security Checklist

Before deploying:

- [ ] API keys stored in environment variables
- [ ] HTTPS enabled for all endpoints
- [ ] Rate limiting configured
- [ ] Input validation enabled
- [ ] Logging doesn't expose sensitive data
- [ ] Dependencies updated
- [ ] Security headers configured
- [ ] CORS properly configured

## 📚 Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://bandit.readthedocs.io/)
- [MCP Security Guidelines](https://modelcontextprotocol.io/docs/concepts/security)

## 🆘 Incident Response

In case of a security incident:

1. **Immediate**: Disable affected API keys
2. **Assess**: Determine scope of impact
3. **Contain**: Limit further damage
4. **Notify**: Contact `security@compoid.com`
5. **Remediate**: Apply fixes
6. **Review**: Post-incident analysis

## 📞 Contact

- **Security Reports**: `security@compoid.com`
- **General Questions**: [GitHub Discussions](https://github.com/compoid/compoid-mcp/discussions)
- **Urgent Matters**: Contact maintainers directly

---

**Last Updated**: March 4, 2026  
**Version**: 1.0.0
