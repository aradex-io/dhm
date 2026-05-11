> **Status:** Phase 1 (initial release) is shipped as v0.1.0. Items below remain as the historical roadmap.

# Dependency Health Monitor - Project Roadmap

**Document Date:** 26 January 2026
**Version:** 1.0
**Status:** Planning Phase

---

## Executive Summary

This roadmap outlines the phased development approach for the Dependency Health Monitor (DHM), a Python library and CLI tool that provides comprehensive health assessments for project dependencies. The project is structured to deliver incremental value while building toward a complete dependency governance solution.

---

## Phase 1: Foundation (MVP)

### Objectives
- Establish core health scoring infrastructure
- Support common dependency file formats
- Integrate with PyPI and GitHub APIs
- Provide basic CLI functionality
- Publish initial PyPI release

### Deliverables

#### 1.1 Core Data Models
- [ ] `PackageIdentifier` with name, version, extras
- [ ] `HealthScore` with component scores and grade
- [ ] `Vulnerability` data structure
- [ ] `MaintenanceStatus` enumeration
- [ ] `DependencyReport` composite type

#### 1.2 Dependency Resolution
- [ ] `requirements.txt` parser
- [ ] `pyproject.toml` parser (PEP 621)
- [ ] Basic version constraint handling
- [ ] Duplicate dependency deduplication

#### 1.3 Data Collectors
- [ ] PyPI JSON API client
  - [ ] Package metadata fetching
  - [ ] Release history retrieval
  - [ ] Download statistics
- [ ] GitHub API client
  - [ ] Repository metadata
  - [ ] Basic activity metrics
  - [ ] Archive status detection
- [ ] OSV vulnerability database client

#### 1.4 Health Calculator
- [ ] Security score (vulnerability-based)
- [ ] Maintenance score (release recency, commit activity)
- [ ] Community score (stars, contributors, forks)
- [ ] Popularity score (downloads, dependents)
- [ ] Weighted overall score algorithm
- [ ] Letter grade conversion (A-F)

#### 1.5 Basic CLI
- [ ] `dhm scan <path>` - Scan project dependencies
- [ ] `dhm check <package>` - Check single package
- [ ] `--format` output options (table, JSON)
- [ ] `--fail-on` threshold for CI/CD

#### 1.6 Cache Layer
- [ ] SQLite-based response cache
- [ ] TTL-based expiration
- [ ] ETag support for conditional requests

#### 1.7 Documentation & Release
- [ ] README with quickstart guide
- [ ] API documentation
- [ ] PyPI package publication
- [ ] GitHub repository with CI/CD

### Success Criteria
- Parse 3+ dependency file formats
- Score packages with >90% accuracy vs. manual assessment
- CLI works smoothly for typical Python projects
- Test coverage >80%

---

## Phase 2: Enhanced Analysis

### Objectives
- Expand dependency file format support
- Add vulnerability scanning from multiple sources
- Implement alternatives recommendation
- Improve scoring accuracy

### Deliverables

#### 2.1 Additional Parsers
- [ ] `poetry.lock` parser
- [ ] `Pipfile` / `Pipfile.lock` parser
- [ ] `setup.py` parser (legacy)
- [ ] `setup.cfg` parser
- [ ] Conda `environment.yml` parser

#### 2.2 Transitive Dependency Support
- [ ] Build dependency tree
- [ ] Identify direct vs. transitive dependencies
- [ ] Track what depends on what
- [ ] Highlight transitive vulnerabilities

#### 2.3 Enhanced Vulnerability Scanning
- [ ] PyUp Safety database integration
- [ ] GitHub Advisory Database integration
- [ ] NVD/CVE database integration
- [ ] Vulnerability deduplication across sources
- [ ] CVSS score integration

#### 2.4 Alternatives Recommender
- [ ] Known alternatives database
- [ ] Similar package search
- [ ] Health comparison scoring
- [ ] Migration effort estimation
- [ ] API compatibility hints

#### 2.5 GitLab Support
- [ ] GitLab API client
- [ ] Repository metrics collection
- [ ] Self-hosted GitLab support

#### 2.6 Enhanced Scoring
- [ ] Code quality signals (CI status, test coverage)
- [ ] License compatibility checking
- [ ] Python version compatibility
- [ ] Dependency depth penalties
- [ ] Bus factor estimation

### Success Criteria
- Support 8+ dependency file formats
- Find vulnerabilities from 4+ sources
- Recommend alternatives with >70% user acceptance
- Handle projects with 200+ dependencies

---

## Phase 3: CI/CD Integration

### Objectives
- Seamless integration with popular CI/CD platforms
- Policy-based dependency governance
- Multiple report formats for different consumers
- Pre-commit hook support

### Deliverables

#### 3.1 CI/CD Platform Support
- [ ] GitHub Actions integration
  - [ ] Reusable workflow
  - [ ] PR comments with health summary
  - [ ] Status checks
- [ ] GitLab CI integration
  - [ ] `.gitlab-ci.yml` template
  - [ ] Merge request integration
- [ ] Jenkins plugin
- [ ] Azure DevOps extension

#### 3.2 Report Formats
- [ ] SARIF format (GitHub Security)
- [ ] JUnit XML (CI test results)
- [ ] HTML report with charts
- [ ] Markdown for PR comments
- [ ] JSON for programmatic use
- [ ] CSV for spreadsheet analysis

#### 3.3 Policy Engine
- [ ] Configurable thresholds
- [ ] Package allowlist/blocklist
- [ ] Vulnerability exception management
- [ ] License policy enforcement
- [ ] Age-based policies (no packages older than X)

#### 3.4 Pre-commit Integration
- [ ] Pre-commit hook definition
- [ ] Fast mode for quick checks
- [ ] Cached results for speed

#### 3.5 Configuration Management
- [ ] `pyproject.toml` configuration section
- [ ] `.dhm.toml` standalone config
- [ ] Environment variable support
- [ ] Configuration inheritance

### Success Criteria
- One-line CI/CD integration
- Policy violations block PRs automatically
- Reports render correctly in all platforms
- Pre-commit runs in <5 seconds

---

## Phase 4: Enterprise Features

### Objectives
- Support for private/internal packages
- Team collaboration features
- Compliance and audit capabilities
- Performance at scale

### Deliverables

#### 4.1 Private Registry Support
- [ ] Private PyPI servers (devpi, Artifactory)
- [ ] Authentication for private registries
- [ ] Internal package health tracking
- [ ] Custom metadata sources

#### 4.2 Compliance Features
- [ ] SBOM generation (SPDX, CycloneDX)
- [ ] License compliance reporting
- [ ] Audit trail for exceptions
- [ ] Historical health tracking
- [ ] Compliance dashboard

#### 4.3 Team Features
- [ ] Shared policy configurations
- [ ] Team-wide exception management
- [ ] Role-based policy administration
- [ ] Cross-project aggregation

#### 4.4 Performance Optimization
- [ ] Parallel API requests
- [ ] Incremental scanning (only changed deps)
- [ ] Distributed caching (Redis)
- [ ] Background pre-caching

#### 4.5 API Server Mode
- [ ] REST API for integrations
- [ ] Webhook support
- [ ] Rate limiting
- [ ] API key management

### Success Criteria
- Handle private package registries seamlessly
- Generate compliant SBOM documents
- Support organizations with 100+ projects
- API response times <500ms

---

## Phase 5: Intelligence & Insights

### Objectives
- Predictive health analysis
- Trend detection and forecasting
- Smart recommendations
- Ecosystem-wide insights

### Deliverables

#### 5.1 Trend Analysis
- [ ] Health score over time tracking
- [ ] Maintenance trajectory prediction
- [ ] Abandonment risk scoring
- [ ] Ecosystem trend reports

#### 5.2 Smart Recommendations
- [ ] Proactive upgrade suggestions
- [ ] Risk-based prioritization
- [ ] Automated PR creation for updates
- [ ] Breaking change detection

#### 5.3 Dependency Insights
- [ ] Popular combination analysis
- [ ] Conflict prediction
- [ ] Supply chain risk mapping
- [ ] Typosquatting detection

#### 5.4 Reporting Dashboard
- [ ] Web-based dashboard
- [ ] Organization-wide views
- [ ] Drill-down capabilities
- [ ] Custom report builder

#### 5.5 Integrations
- [ ] Slack/Teams notifications
- [ ] Jira issue creation
- [ ] PagerDuty alerts
- [ ] Custom webhook actions

### Success Criteria
- Predict abandonment 6+ months in advance
- Reduce false positives to <5%
- Dashboard used by >50% of enterprise users
- Actionable insights drive real improvements

---

## Technical Milestones

| Milestone | Target | Key Deliverable |
|-----------|--------|-----------------|
| Alpha Release | Phase 1 Complete | Basic CLI, PyPI health checks |
| Beta Release | Phase 2 Complete | Full scanning, alternatives |
| 1.0 Release | Phase 3 Complete | CI/CD ready, policy engine |
| Enterprise | Phase 4 Complete | Private registries, compliance |
| Intelligence | Phase 5 Complete | Predictions, dashboard |

---

## Risk Mitigation

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| API rate limiting | High | Medium | Aggressive caching, token rotation, fallbacks |
| Data source changes | Medium | High | Abstract data layer, multiple sources |
| Scoring inaccuracy | Medium | High | User feedback loop, tuneable weights |
| Performance at scale | Medium | Medium | Early benchmarking, optimization budget |

### Market Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Snyk/Dependabot expansion | Medium | High | Focus on scoring depth, not just vulns |
| Low enterprise adoption | Medium | Medium | Strong free tier, clear upgrade path |
| Community contribution | Medium | Low | Good documentation, welcoming culture |

---

## Resource Requirements

### Phase 1 (MVP)
- Primary developer: Full-time equivalent
- API costs: Minimal (free tiers)
- Infrastructure: None (local only)

### Phase 2-3
- Core team: 2 developers
- API costs: ~$50/month (rate limit headroom)
- CI/CD: GitHub Actions free tier

### Phase 4-5
- Expanded team: 3-4 developers
- Infrastructure: Cloud hosting for API server
- Support: Part-time for enterprise users

---

## Success Metrics

### Adoption Metrics
- PyPI weekly downloads
- GitHub stars and forks
- Active GitHub issues/PRs
- CI/CD integration count

### Quality Metrics
- Vulnerability detection accuracy
- False positive rate
- User-reported bugs per release
- Test coverage percentage

### Impact Metrics
- Vulnerabilities prevented (user reports)
- Abandoned packages detected early
- Time saved vs. manual checks
- User satisfaction surveys

### Community Metrics
- Discord/community members
- External blog posts/tutorials
- Conference talk mentions
- Plugin/extension count

---

## Competitive Positioning

### Market Landscape

| Tool | Focus | Weakness |
|------|-------|----------|
| Dependabot | Automated updates | No health scoring |
| Snyk | Security vulnerabilities | Expensive, narrow focus |
| pip-audit | Vulnerability scanning | Single source, no context |
| Safety | Vulnerability database | No maintenance insights |
| Libraries.io | Ecosystem data | Not actionable, API focus |

### DHM Differentiation

1. **Holistic Health Scoring** - Not just vulnerabilities, but maintenance, community, and popularity
2. **Actionable Recommendations** - Every problem comes with a suggested solution
3. **Developer-First** - Library and CLI, not just a service
4. **Transparent Scoring** - Open algorithm, explainable results
5. **CI/CD Native** - Built for automation from day one

---

## Appendix: API Rate Limits

| Service | Free Tier | Authenticated | Strategy |
|---------|-----------|---------------|----------|
| PyPI | Unlimited | N/A | Cache aggressively |
| GitHub | 60/hour | 5000/hour | Require auth for heavy use |
| GitLab | 60/hour | 2000/hour | Support tokens |
| OSV | Unlimited | N/A | Cache responses |
| Libraries.io | 60/hour | Varies | Optional enhancement |

---

## Appendix: Health Score Algorithm

```
Security Score (0-100):
  Base: 100
  Per CRITICAL vuln: -40
  Per HIGH vuln: -25
  Per MEDIUM vuln: -10
  Per LOW vuln: -5

Maintenance Score (0-100):
  Base: 50
  Release < 30 days: +20
  Release < 90 days: +15
  Release < 180 days: +10
  Release < 365 days: +5
  Release > 2 years: -10
  Commits/day (30d) > 1: +15
  Issue close rate > 80%: +10
  Archived: -30

Community Score (0-100):
  Contributors > 100: +30
  Contributors > 20: +25
  Stars > 10000: +30
  Stars > 1000: +25
  PR merge rate > 70%: +20

Popularity Score (0-100):
  Downloads (scaled logarithmically)
  Dependent packages (scaled logarithmically)

Overall = (Security × 0.35) + (Maintenance × 0.30) +
          (Community × 0.20) + (Popularity × 0.15)

Grades:
  A: 90-100
  B: 80-89
  C: 70-79
  D: 60-69
  F: <60
```

---

*This roadmap is a living document and will be updated as the project evolves.*
