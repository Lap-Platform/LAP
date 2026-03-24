# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.6.x   | Yes       |
| < 0.6   | No        |

Only the latest release receives security fixes. We recommend always running the most recent version.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, use GitHub's private vulnerability reporting:

1. Go to the [Security tab](https://github.com/Lap-Platform/lap/security) of this repository
2. Click **"Report a vulnerability"**
3. Fill in the advisory form

### What to include

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Impact assessment (what an attacker could do)
- Any suggested fix, if you have one

### What to expect

- **Acknowledgment** -- within 3 business days
- **Initial assessment** -- within 7 business days
- **Fix timeline** -- depends on severity, but we aim for 30 days for critical issues

We will coordinate with you on disclosure timing. We ask that you do not publicly disclose the vulnerability until a fix is released.

## Out of Scope

The following are not considered security vulnerabilities:

- Spec compilation accuracy or output differences -- use a [bug report](https://github.com/Lap-Platform/lap/issues/new?template=bug-report.yml)
- Denial of service via extremely large input files (LAP is a local CLI tool)
- Issues in dependencies -- report those upstream, but let us know if they affect LAP

## Credit

We appreciate responsible disclosure and will credit reporters in the release notes (unless you prefer to remain anonymous).
